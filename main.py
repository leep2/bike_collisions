import pandas as pd
import requests
import credentials
import numpy as np
from stravalib import client
import polyline
import pickle
import bisect

df = pd.read_csv('CollisionRecords.txt')

df['intersection'] = (df['PRIMARY_RD'].str.split() + ['and'] + df['SECONDARY_RD'].str.split() + ['san', 'francisco']).str.join('+')
intersection = df['intersection'].values

for i, x in enumerate(intersection):
    if '/' in x:
        print i, x

intersection[110] = 'valencia+st+and+18th+st+san+francisco'
intersection[216] = 'de+young+museum+san+francisco'
intersection[226] = 'funston+ave+and+fulton+st+san+francisco'
intersection[243] = 'fulton+st+and+6th+ave+san+francisco'
intersection[315] = 'clipper+st+san+francisco'
intersection[328] = 'columbus+ave+and+FILBERT+ST+san+francisco'
intersection[463] = '7th+st+san+francisco'
intersection[537] = 'willard+st+san+francisco'
intersection[605] = 'fort+point+san+francisco'
for i in xrange(607, 612):
    intersection[i] = 'fort+point+san+francisco'

incidents = len(intersection)
lat_lon = np.zeros([incidents, 2])
for i in range(incidents):
    r = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?query=' + intersection[i] + '&key=' + credentials.key['google'])
    location = r.json()['results'][0]['geometry']['location']
    lat_lon[i][0] = location['lat']
    lat_lon[i][1] = location['lng']

with open('incident_list.pkl', 'wb') as fp:
    pickle.dump(lat_lon, fp)

lat_grid = np.linspace(37.706, 37.814, 5)
lon_grid = np.linspace(-122.519, -122.354, 7)

incident_grid = np.zeros([incidents, 2])
for i in range(incidents):
    incident_grid[i][0] = bisect.bisect(lat_grid, lat_lon[i][0]) - 1
    incident_grid[i][1] = bisect.bisect(lon_grid, lat_lon[i][1]) - 1

df_incident = pd.DataFrame(incident_grid)
df_incident[2] = 1

strava = client.Client(access_token = credentials.key['strava'])

segment_list = []
for x in range(len(lat_grid) - 1):
    for y in range(len(lon_grid) - 1):
        explore = strava.explore_segments([lat_grid[x], lon_grid[y], lat_grid[x + 1], lon_grid[y + 1]])
        for e in explore:
            segment_list.append(e.id)

with open('segment_list.pkl', 'wb') as fp:
    pickle.dump(segment_list, fp)

seg_obj_list = []
for s in segment_list:
    seg = strava.get_segment(s)
    seg_obj_list.append(seg)

effort = np.zeros([len(seg_obj_list), 3])
for i in range(len(seg_obj_list)):
    effort[i][0] = bisect.bisect(lat_grid, seg_obj_list[i].start_latlng[0]) - 1
    effort[i][1] = bisect.bisect(lon_grid, seg_obj_list[i].start_latlng[1]) - 1
    adj_year = 365.0 / (seg_obj_list[i].updated_at - seg_obj_list[i].created_at).days
    effort[i][2] = seg_obj_list[i].effort_count * adj_year

df_effort = pd.DataFrame(data = effort)
mean_effort = df_effort.groupby([0, 1], as_index = False).mean()
sum_effort = df_effort.groupby([0, 1], as_index = False).sum()
max_effort = df_effort.groupby([0, 1], as_index = False).max()

incident_group = df_incident.groupby([0, 1], as_index = False).count()

incident_mean = incident_group.merge(mean_effort, left_on = [0, 1], right_on = [0, 1])
incident_mean.columns = [0, 1, 'inc', 'mean']
incident_max = incident_mean.merge(max_effort, left_on = [0, 1], right_on = [0, 1])
incident_max.columns = [0, 1, 'inc', 'mean', 'max']
incident_sum = incident_max.merge(sum_effort, left_on = [0, 1], right_on = [0, 1])
incident_sum.columns = [0, 1, 'inc', 'mean', 'max', 'sum']
incident_sum['inc_mean'] = incident_sum['inc'] / incident_sum['mean']
incident_sum['inc_max'] = incident_sum['inc'] / incident_sum['max']
incident_sum['inc_sum'] = incident_sum['inc'] / incident_sum['sum']
