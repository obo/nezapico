# TODO

- as soon as relay is set to ON, set watchdog (otherwise risking stuck while heating)
- try-json, on fail ignore troubles

# Usage

- Record temperatures from mid and top tank thermometer along with what our sensor says.
- Run ``make`` to plot temp-correlations.tab.


# Temperatures correlations

Seems that 32 on our sensor could be the value of about 40 on the hardware dialer.

# Debugging
2022-09-17
trying to locate the crashes, running in debug mode, it stopped here:
Idling... Water:  29.125 ; House:  19.8125 ; Board:  27.0444 ; Up:  6.911944 ; HoursOperated:  0.0
100 138 0
100 138 0
Idling... Water:  29.125 ; House:  19.8125 ; Board:  27.0444 ; Up:  6.912222 ; HoursOperated:  0.0
100 138 0
100 138 0
Idling... Water:  29.125 ; House:  19.8125 ; Board:  27.0444 ; Up:  6.912778 ; HoursOperated:  0.0
100 138 0
100 138 0
Client connected from ('195.113.18.162', 47264)
Done serving
Idling... Water:  29.125 ; House:  19.8125 ; Board:  27.0444 ; Up:  6.913055 ; HoursOperated:  0.0
Read temperatures, should heat?  False ; heating running?  False
100 138 0
100 138 0
Idling... Water:  29.125 ; House:  19.875 ; Board:  27.0444 ; Up:  6.913889 ; HoursOperated:  0.0
100 138 0
...
Idling... Water:  28.75 ; House:  19.875 ; Board:  27.0444 ; Up:  7.035278 ; HoursOperated:  0.0
100 143 0
100 143 0
Idling... Water:  28.75 ; House:  19.875 ; Board:  27.0444 ; Up:  7.035555 ; HoursOperated:  0.0
Read temperatures, should heat?  False ; heating running?  False
100 143 0
100 143 0
Client connected from ('172.104.242.173', 57537)

Connection lost (device reports readiness to read but returned no data (device disconnected or multiple access on port?))

Is successfully served once instance at 7.013333 (20220917-0609) uptime and then died at uptime 7.035555 during another serving. Curiously, this was at 20220917-0612, the uptime was 0.0225. So the restart seems to have happenned **during** the request. But it was 81 seconds. Actually, it was possibly a ping of death!! From someone else 172.104.242.173.
