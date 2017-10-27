import pandas as pd
import numpy as np
import requests
import credentials

df = pd.read_csv('CollisionRecords.txt')
df = df[df['BICYCLE_ACCIDENT'] == 'Y']
df['intersection'] = (df['PRIMARY_RD'].str.split() + ['and'] + df['SECONDARY_RD'].str.split() + ['san', 'francisco']).str.join('+')
inters = df['intersection'].values

geo = []
errors = []

for i, inte in enumerate(inters):
    r = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?query=' + inte + '&key=' + credentials.key['google'])
    if r.json()['status'] == 'OK':
        row = []
        location = r.json()['results'][0]['geometry']['location']
        row.append(location['lat'])
        row.append(location['lng'])
        geo.append(row)
    else:
        errors.append(inte)
    print i

geo_arr = np.array(geo)
errors_arr = np.array(errors)
np.savetxt('geo.csv', geo_arr, delimiter = ',')
np.savetxt('errors.txt', errors_arr, fmt = '%s')
