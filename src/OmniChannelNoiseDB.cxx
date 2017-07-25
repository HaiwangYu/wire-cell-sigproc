#include "WireCellSigProc/OmniChannelNoiseDB.h"
#include "WireCellUtil/Response.h"
#include "WireCellUtil/NamedFactory.h"

#include <cmath>

WIRECELL_FACTORY(OmniChannelNoiseDB, WireCell::SigProc::OmniChannelNoiseDB,
                 WireCell::IChannelNoiseDatabase, WireCell::IConfigurable);

using namespace WireCell;
using namespace WireCell::SigProc;


OmniChannelNoiseDB::OmniChannelNoiseDB()
    : m_tick(0.5*units::us)
    , m_nsamples(9600)
{
}
OmniChannelNoiseDB::~OmniChannelNoiseDB()
{
}

OmniChannelNoiseDB::ChannelInfo::ChannelInfo()
    : chid(-1)
    , nominal_baseline(0.0)
    , gain_correction(1.0)
    , response_offset(0.0)
    , min_rms_cut(0.5)
    , max_rms_cut(10.0)
    , pad_window_front(0.0)
    , pad_window_back(0.0)
    , rcrc(nullptr)
    , config(nullptr)
    , noise(nullptr)
    , response(nullptr)
{
}



WireCell::Configuration OmniChannelNoiseDB::default_configuration() const
{
    Configuration cfg;
    cfg["tick"] = m_tick;
    cfg["nsamples"] = m_nsamples;
    cfg["anode"] = "AnodePlane";

    /// These must be provided
    cfg["groups"] = Json::arrayValue;
    cfg["channel_info"] = Json::arrayValue;
    
    return cfg;
}


/*
  Interpret and return a list of channels for JSON like:

  // just one channel
  channels: 42,

  or

  // explicit list of channels
  channels: [1,42,107],

  or

  // inclusive range of channels
  channels: { first: 0, last: 2400 },

  or

  // all channels in a wire plane
  channels: { wpid: wc.WirePlaneId(wc.kWlayer) },
*/
std::vector<int> OmniChannelNoiseDB::parse_channels(const Json::Value& jchannels)
{
    std::vector<int> ret;

    // single channel
    if (jchannels.isInt()) {
        ret.push_back(jchannels.asInt());
        return ret;
    }

    // array of explicit channels
    if (jchannels.isArray()) {
        const int nch = jchannels.size();
        ret.resize(nch);
        for (int ind=0; ind<nch; ++ind) {
            ret[ind] = jchannels[ind].asInt();
        }
        return ret;
    }

    // else, assume an object

    // range
    if (jchannels.isMember("first") && jchannels.isMember("last")) {
        const int chf = jchannels["first"].asInt();
        const int chl = jchannels["last"].asInt();
        const int nch = chl-chf+1;
        ret.resize(nch);
        for (int ind=0; ind < nch; ++ind) {
            ret[ind] = chf + ind;
        }
        return ret;
    }
    
    // wire plane id
    if (jchannels.isMember("wpid")) {
        WirePlaneId wpid(jchannels["wpid"].asInt());
        for (auto ch : m_anode->channels()) {
            if (m_anode->resolve(ch) == wpid) {
                ret.push_back(ch);
            }
        }
        return ret;
    }

    return ret;
}

OmniChannelNoiseDB::shared_filter_t OmniChannelNoiseDB::make_filter(std::complex<float> defval)
{
    return std::make_shared<filter_t>(m_nsamples, defval);
}
OmniChannelNoiseDB::shared_filter_t OmniChannelNoiseDB::default_filter()
{
    static shared_filter_t def = make_filter();
    return def;
}

OmniChannelNoiseDB::shared_filter_t OmniChannelNoiseDB::parse_freqmasks(Json::Value jfm)
{
    if (jfm.isNull()) {
        return default_filter();
    }

    auto spectrum = make_filter(std::complex<float>(1,0));
    for (auto jone : jfm) {
        double value = jone["value"].asDouble();
        int lo = std::max(jone["lobin"].asInt(), 0);
        int hi = std::min(jone["hibin"].asInt(), m_nsamples-1);
        // std::cerr << "freqmasks: set [" << lo << "," << hi << "] to " << value << std::endl;
        for (int ind=lo; ind <= hi; ++ind) { // inclusive
            spectrum->at(ind) = value;
        }
    }
    return spectrum;
}

OmniChannelNoiseDB::shared_filter_t OmniChannelNoiseDB::parse_rcrc(Json::Value jrcrc)
{
    if (jrcrc.isNull()) {
        return default_filter();
    }
    const double rcrc = jrcrc.asDouble();
    const int key = int(round(1000*rcrc/units::ms));
    auto it = m_rcrc_cache.find(key);
    if (it != m_rcrc_cache.end()) {
        return it->second;
    }

    Response::SimpleRC rcres(rcrc, m_tick);
    auto signal = rcres.generate(WireCell::Binning(m_nsamples, 0, m_nsamples*m_tick));
    
    Waveform::compseq_t spectrum = Waveform::dft(signal);
    // get the square of it because there are two RC filters
    Waveform::compseq_t spectrum2 = spectrum;
    Waveform::scale(spectrum2,spectrum);
    

    // std::cerr << "OmniChannelNoiseDB:: get rcrc as: " << rcrc 
    //           << " sum=" << Waveform::sum(spectrum2)
    //           << std::endl;

    auto ret = std::make_shared<filter_t>(spectrum2);
    m_rcrc_cache[key] = ret;
    return ret;
}

double OmniChannelNoiseDB::parse_gain(Json::Value jreconfig)
{
    if (jreconfig.empty()) {
        return 1.0;
    }

    const double from_gain = jreconfig["from"]["gain"].asDouble();
    const double to_gain = jreconfig["to"]["gain"].asDouble();
    return to_gain/from_gain;
}

OmniChannelNoiseDB::shared_filter_t OmniChannelNoiseDB::parse_reconfig(Json::Value jreconfig)
{
    if (jreconfig.empty()) {
        return default_filter();
    }

    const double from_gain = jreconfig["from"]["gain"].asDouble();
    const double from_shaping = jreconfig["from"]["shaping"].asDouble();
    const double to_gain = jreconfig["to"]["gain"].asDouble();
    const double to_shaping = jreconfig["to"]["shaping"].asDouble();


    // kind of evil.
    int key = int(round(10.0*from_gain/(units::mV/units::fC))) << 24
        | int(round(10.0*from_shaping/units::us)) << 16
        | int(round(10.0*to_gain/(units::mV/units::fC))) << 8
        | int(round(10.0*to_shaping/units::us)) << 16;
        
    // std::cerr << "KEY:" << key
    //           << " fg="<<from_gain/(units::mV/units::fC) << " mV/fC,"
    //           << " fs=" << from_shaping/units::us << " us,"
    //           << " tg="<<to_gain/(units::mV/units::fC) << " mV/fC,"
    //           << " ts="<<to_shaping/units::us << " us,"
    //           << " m_tick=" << m_tick/units::us << " us."
    //           << std::endl;


    auto it = m_reconfig_cache.find(key);
    if (it != m_reconfig_cache.end()) {
        return it->second;
    }

    Response::ColdElec from_ce(from_gain, from_shaping);
    Response::ColdElec to_ce(to_gain, to_shaping);
    auto to_sig   =   to_ce.generate(WireCell::Binning(m_nsamples, 0, m_nsamples*m_tick));
    auto from_sig = from_ce.generate(WireCell::Binning(m_nsamples, 0, m_nsamples*m_tick));

    
    auto to_filt   = Waveform::dft(to_sig);
    auto from_filt = Waveform::dft(from_sig);

    auto from_filt_sum = Waveform::sum(from_filt);
    auto to_filt_sum   = Waveform::sum(to_filt);

    Waveform::shrink(to_filt, from_filt); // divide
    auto filt = std::make_shared<filter_t>(to_filt);

    // std::cerr << "OmniChannelNoiseDB: "
    //           << " from_sig sum=" << Waveform::sum(from_sig)
    //           << " to_sig sum=" << Waveform::sum(to_sig)
    //           << " from_filt sum=" << from_filt_sum
    //           << " to_filt sum=" << to_filt_sum
    //           << " rat_filt sum=" << Waveform::sum(to_filt)
    //           << std::endl;


    m_reconfig_cache[key] = filt;
    return filt;
}
OmniChannelNoiseDB::shared_filter_t OmniChannelNoiseDB::parse_response(Json::Value jreconfig)
{
    if (jreconfig.isMember("wpid")) {
        WirePlaneId wpid(jreconfig["wpid"].asInt());
        auto it = m_response_cache.find(wpid.ident());
        if (it != m_response_cache.end()) {
            return it->second;
        }
        // fixme: move to this.  See bug #4 in iface
        //auto wp = m_anode->face(wpid)->plane(wpid);
        // for now:   
        auto wp = m_anode->face(wpid.face())->plane(wpid.index());
        auto const& fr = wp->pir()->field_response();
        auto fravg = Response::wire_region_average(fr);
        auto const& pr = fravg.planes[wpid.index()];

        // full length waveform
        std::vector<float> waveform(m_nsamples, 0.0);
        for (auto const& path : pr.paths) {
            auto const& current = path.current;
            const size_t nsamp = std::min(m_nsamples, (int)current.size());
            for (size_t ind=0; ind<nsamp; ++ind) {
                waveform[ind] += current[ind];
            }
        }
        auto spectrum = WireCell::Waveform::dft(waveform);
        auto ret = std::make_shared<filter_t>(spectrum);
        m_response_cache[wpid.ident()] = ret;
        return ret;
    }

    if (jreconfig.isMember("waveform") && jreconfig.isMember("waveformid")) {
        int id = jreconfig["waveformid"].asInt();
        auto it = m_waveform_cache.find(id);
        if (it != m_waveform_cache.end()) {
            return it->second;
        }
        
        auto jwave = jreconfig["waveform"];
        const int nsamp = std::min(m_nsamples, (int)jwave.size());

        // Explicitly given waveform
        std::vector<float> waveform(m_nsamples, 0.0);
        for (int ind=0; ind<nsamp; ++ind) {
            waveform[ind] = jwave[ind].asFloat();
        }
        
        auto spectrum = WireCell::Waveform::dft(waveform);
        auto ret = std::make_shared<filter_t>(spectrum);
        m_waveform_cache[id] = ret;
        return ret;
    }

    // this default return is special in that it's empty instead of
    // being a flat, unity spectrum.
    static shared_filter_t empty = std::make_shared<filter_t>();
    return empty;
}


OmniChannelNoiseDB::ChannelInfo& OmniChannelNoiseDB::get_ci(int chid)
{
    return m_db.at(chid);
}

template<typename Type>
void dump_cfg(const std::string& name, std::vector<int> chans, Type val)
{
    std::sort(chans.begin(), chans.end());
    // std::cerr << "OmniChannelNoiseDB: setting " << name << " to " << val << " on " << chans.size() << ":[" << chans.front() << "," << chans.back() << "]\n";
}

void OmniChannelNoiseDB::update_channels(Json::Value cfg)
{
    auto chans = parse_channels(cfg["channels"]);

    if (cfg.isMember("nominal_baseline")) {
        double val = cfg["nominal_baseline"].asDouble();
        dump_cfg("baseline", chans, val);
        for (int ch : chans) {
            m_db.at(ch).nominal_baseline = val;
        }
    }
    if (cfg.isMember("gain_correction")) {
        double val = cfg["gain_correction"].asDouble();
        dump_cfg("gain", chans, val);
        for (int ch : chans) {
            m_db.at(ch).gain_correction = val;
        }
    }
    // fixme: why have two ways to set the same thing?  
    {                           
        auto jfilt = cfg["reconfig"];
        if (!jfilt.isNull()) {
            auto val = parse_gain(jfilt);
            dump_cfg("gain", chans, val);
            for (int ch : chans) {
                m_db.at(ch).gain_correction = val;
            }
        }
    }

    if (cfg.isMember("response_offset")) {
        double val = cfg["response_offset"].asDouble();
        dump_cfg("offset", chans, val);
        for (int ch : chans) {
            m_db.at(ch).response_offset = val;
        }
    }
    if (cfg.isMember("min_rms_cut")) {
        double val = cfg["min_rms_cut"].asDouble();
        dump_cfg("minrms", chans, val);
        for (int ch : chans) {
            m_db.at(ch).min_rms_cut = val;
        }
    }
    if (cfg.isMember("max_rms_cut")) {
        double val = cfg["max_rms_cut"].asDouble();
        dump_cfg("maxrms", chans, val);
        for (int ch : chans) {
            m_db.at(ch).max_rms_cut = val;
        }
    }
    if (cfg.isMember("pad_window_front")) {
        int val = cfg["pad_window_front"].asDouble();
        dump_cfg("padfront", chans, val);
        for (int ch : chans) {
            m_db.at(ch).pad_window_front = val;
        }
    }
    if (cfg.isMember("pad_window_back")) {
        int val = cfg["pad_window_back"].asDouble();
        dump_cfg("padback", chans, val);
        for (int ch : chans) {
            m_db.at(ch).pad_window_back = val;
        }
    }
    {
        auto jfilt = cfg["rcrc"];
        if (!jfilt.isNull()) {
            auto val = parse_rcrc(jfilt);
            dump_cfg("rcrc", chans, Waveform::sum(*val));
            for (int ch : chans) {
                m_db.at(ch).rcrc = val;
            }
        }
    }
    {
        auto jfilt = cfg["reconfig"];
        if (!jfilt.isNull()) {
            auto val = parse_reconfig(jfilt);
            dump_cfg("reconfig", chans, Waveform::sum(*val));
            for (int ch : chans) {
                m_db.at(ch).config = val;
            }
        }
    }
    {
        auto jfilt = cfg["freqmasks"];
        if (!jfilt.isNull()) {
            auto val = parse_freqmasks(jfilt);
            dump_cfg("freqmasks", chans, Waveform::sum(*val));
            // std::cerr << jfilt << std::endl;
            for (int ch : chans) {
                m_db.at(ch).noise = val;
            }
        }
    }
    {
        auto jfilt = cfg["response"];
        if (!jfilt.isNull()) {
            auto val = parse_response(jfilt);
            dump_cfg("response", chans, Waveform::sum(*val));
            for (int ch : chans) {
                m_db.at(ch).response = val;
            }
        }
    }

}


void OmniChannelNoiseDB::configure(const WireCell::Configuration& cfg)
{
    m_tick = get(cfg, "tick", m_tick);
    m_nsamples = get(cfg, "nsamples", m_nsamples);
    std::string anode_tn = get<std::string>(cfg, "anode", "AnodePlane");
    m_anode = Factory::find_tn<IAnodePlane>(anode_tn);

    // WARNING: this assumes channel numbers count from 0 with not gaps!
    int nchans = m_anode->channels().size();
    std::cerr << "noise database with " << nchans << " channels\n";
    m_db.resize(nchans);

    m_channel_groups.clear();
    auto jgroups = cfg["groups"];
    for (auto jgroup: jgroups) {
        std::vector<int> channel_group;
        for (auto jch: jgroup) {
            channel_group.push_back(jch.asInt());
        }
        m_channel_groups.push_back(channel_group);
    }
    m_bad_channels.clear();
    for (auto jch : cfg["bad"]) {
        m_bad_channels.push_back(jch.asInt());
    }
    std::sort(m_bad_channels.begin(), m_bad_channels.end());
    std::cerr << "OmniChannelNoiseDB: setting "<<m_bad_channels.size()
              << ":[" << m_bad_channels.front() << "," << m_bad_channels.back() << "]"
              <<" bad channels\n";

    
    for (auto jci : cfg["channel_info"]) {
        update_channels(jci);
    }
}





int OmniChannelNoiseDB::number_samples() const
{
    return m_nsamples;
}
double OmniChannelNoiseDB::sample_time() const
{
    return m_tick;
}



double OmniChannelNoiseDB::nominal_baseline(int channel) const
{
    return dbget(channel).nominal_baseline;
}

double OmniChannelNoiseDB::gain_correction(int channel) const
{
    return dbget(channel).gain_correction;
}

double OmniChannelNoiseDB::response_offset(int channel) const
{
    return dbget(channel).response_offset;
}

double OmniChannelNoiseDB::min_rms_cut(int channel) const
{
    return dbget(channel).min_rms_cut;
}

double OmniChannelNoiseDB::max_rms_cut(int channel) const
{
    return dbget(channel).max_rms_cut;
}

int OmniChannelNoiseDB::pad_window_front(int channel) const
{
    return dbget(channel).pad_window_front;
}

int OmniChannelNoiseDB::pad_window_back(int channel) const
{
    return dbget(channel).pad_window_back;
}

const IChannelNoiseDatabase::filter_t& OmniChannelNoiseDB::rcrc(int channel) const
{
    return *(dbget(channel).rcrc);
}

const IChannelNoiseDatabase::filter_t& OmniChannelNoiseDB::config(int channel) const
{
    auto filt = dbget(channel).config;
    //std::cerr << "OmniChannelNoiseDB::config("<<channel<<") sum = " << Waveform::sum(*filt) << std::endl;
    //return *(dbget(channel).config);
    return *filt;
}

const IChannelNoiseDatabase::filter_t& OmniChannelNoiseDB::noise(int channel) const
{
    return *(dbget(channel).noise);
}
	
const IChannelNoiseDatabase::filter_t& OmniChannelNoiseDB::response(int channel) const
{
    return *(dbget(channel).response);
}


// Local Variables:
// mode: c++
// c-basic-offset: 4
// End: