
2: 30, 3: 34.4, hlasi vodu 28.6 voda sotva odrazena
2: 52, 3: 57.2, hlasi vody 44.6, voda na ruce bezva horka   slunce sviti, solar nestahuje

2: 58.2,  3: 63.2,  Hlasil 48.8

2: 53.8, 3:60.2, Water: 46.3125 | House: 18.375

2: 51.7, 3:60.1, w 47.12, h 18.6

2: 28.9, 3:30.0, w:25


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
