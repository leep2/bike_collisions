import pandas as pd
import requests
import credentials
import numpy as np
from stravalib import client
import pickle
import bisect
import gmplot

def read_collision_data():
    df = pd.read_csv('CollisionRecords.txt')
    df = df[df['BICYCLE_ACCIDENT'] == 'Y']
    return df

def collision_intersections(df):
    df['intersection'] = (df['PRIMARY_RD'].str.split() + ['and'] + df['SECONDARY_RD'].str.split() + ['san', 'francisco']).str.join('+')
    inters = df['intersection'].values
    inters[110] = 'valencia+st+and+18th+st+san+francisco'
    inters[216] = 'de+young+museum+san+francisco'
    inters[226] = 'funston+ave+and+fulton+st+san+francisco'
    inters[243] = 'fulton+st+and+6th+ave+san+francisco'
    inters[315] = 'clipper+st+san+francisco'
    inters[328] = 'columbus+ave+and+filbert+st+san+francisco'
    inters[463] = '7th+st+san+francisco'
    inters[537] = 'willard+st+san+francisco'
    inters[605] = 'fort+point+san+francisco'
    for i in range(607, 612):
        inters[i] = 'fort+point+san+francisco'
    return inters, len(inters)

def google_api_geo(inters, num_collisions):
    geo = np.zeros([num_collisions, 2])
    for i in range(num_collisions):
        r = requests.get('https://maps.googleapis.com/maps/api/place/textsearch/json?query=' + inters[i] + '&key=' + credentials.key['google'])
        location = r.json()['results'][0]['geometry']['location']
        geo[i][0] = location['lat']
        geo[i][1] = location['lng']
    np.savetxt('collision_geo.csv', geo, delimiter = ',')
    return geo

def bounding_box(left, bottom, right, top):
    return {'min_lon': left, 'min_lat': bottom, 'max_lon': right, 'max_lat': top}

def lat_lon_grid(bounds, height, width):
    latitude_grid = np.linspace(bounds['min_lat'], bounds['max_lat'], height + 1)
    longitude_grid = np.linspace(bounds['min_lon'], bounds['max_lon'], width + 1)
    return latitude_grid, longitude_grid

def grid(geo, latitude_grid, longitude_grid):
    grid_arr = np.zeros([len(geo), 2])
    for i, g in enumerate(geo):
        grid_arr[i][0] = bisect.bisect(latitude_grid, g[0]) - 1
        grid_arr[i][1] = bisect.bisect(longitude_grid, g[1]) - 1
    return grid_arr

def filter_bounds(arr, height, width):
    mask0a = arr[:, 0] >= 0
    mask0b = arr[:, 0] < height
    mask1a = arr[:, 1] >= 0
    mask1b = arr[:, 1] < width
    return arr[mask0a & mask0b & mask1a & mask1b]

def strava_api_segments(bounds, height, width):
    strava_client = client.Client(access_token = credentials.key['strava'])
    latitude_grid, longitude_grid = lat_lon_grid(bounds, height, width)
    segment_list = []
    for x in range(len(latitude_grid) - 1):
        for y in range(len(longitude_grid) - 1):
            explore = strava_client.explore_segments([latitude_grid[x], longitude_grid[y], latitude_grid[x + 1], longitude_grid[y + 1]])
            for segment in explore:
                segment_list.append(segment.id)
    seg_obj_list = []
    for id in segment_list:
        seg = strava_client.get_segment(id)
        seg_obj_list.append(seg)
    num_segments = len(seg_obj_list)
    segment_detail = np.zeros([num_segments, 4])
    for i, segment in enumerate(seg_obj_list):
        segment_detail[i][0] = segment.start_latlng[0]
        segment_detail[i][1] = segment.start_latlng[1]
        segment_detail[i][2] = (segment.updated_at - segment.created_at).days
        segment_detail[i][3] = segment.effort_count
    np.savetxt('segment_detail.csv', segment_detail, delimiter = ',')
    return segment_detail

def effort_geo_to_grid(grid, eff):
    return np.concatenate([grid, eff[:, 2:]], axis = 1)

def combine_collision_effort(col, eff):
    df_collision = pd.DataFrame(col, columns = ['y', 'x'])
    df_collision['count'] = 1
    collision_count = df_collision.groupby(['y', 'x'], as_index = False).count()
    df_effort = pd.DataFrame(eff, columns = ['y', 'x', 'days', 'efforts'])
    df_effort['adj_efforts'] = df_effort['efforts'] * 365.0 / df_effort['days']
    df_effort = df_effort[['y', 'x', 'adj_efforts']]
    max_effort = df_effort.groupby(['y', 'x'], as_index = False).max()
    mean_effort = df_effort.groupby(['y', 'x'], as_index = False).mean()
    collision_max = collision_count.merge(max_effort, how = 'right', on = ['y', 'x'])
    collision_max.fillna(0, inplace = True)
    collision_max_mean = collision_max.merge(mean_effort, on = ['y', 'x'])
    collision_max_mean.columns = ['y', 'x', 'count', 'max', 'mean']
    collision_max_mean['count_max'] = collision_max_mean['count'] / collision_max_mean['max']
    collision_max_mean['count_mean'] = collision_max_mean['count'] / collision_max_mean['mean']
    collision_max_mean['count_log_max'] = collision_max_mean['count'] / np.log(collision_max_mean['max'])
    collision_max_mean['count_log_mean'] = collision_max_mean['count'] / np.log(collision_max_mean['mean'])
    collision_max_mean['log_count_max'] = np.log(0.001 + collision_max_mean['count'] * 1.0 / collision_max_mean['max'])
    collision_max_mean['log_count_mean'] = np.log(0.001 + collision_max_mean['count'] * 1.0 / collision_max_mean['mean'])
    collision_max_mean['log_max'] = np.log(collision_max_mean['max'])
    collision_max_mean['log_mean'] = np.log(collision_max_mean['mean'])
    print collision_max_mean
    np.savetxt('collision_max_mean.csv', collision_max_mean, delimiter = ',')
    return collision_max_mean

def color_map(df, column, bounds, latitude_grid, longitude_grid):
    color_progression = ['Green', 'YellowGreen', 'Yellow', 'Orange', 'OrangeRed', 'Red']
#    color_progression = ['LightBlue', 'LightSkyBlue', 'CornflowerBlue', 'Blue', 'DarkBlue', 'Navy']
    num_colors = len(color_progression)
    low = df[column].min()
    high = df[column].max()
    df['rel_value'] = (df[column] * 1.0 - low) / (high - low)
    df['color'] = (df['rel_value'] * num_colors).astype(int).clip(upper = num_colors - 1)
    c_map = df[['y', 'x', 'color']].astype(int).values
    center_lat = (bounds['min_lat'] + bounds['max_lat']) * 1.0 / 2
    center_lon = (bounds['min_lon'] + bounds['max_lon']) * 1.0 / 2
    gmap = gmplot.GoogleMapPlotter(center_lat, center_lon, 12)
    for row in c_map:
        s = latitude_grid[row[0]]
        n = latitude_grid[row[0] + 1]
        w = longitude_grid[row[1]]
        e = longitude_grid[row[1] + 1]
        gmap.polygon([s, n, n, s], [w, w, e, e], color = color_progression[row[2]])
    gmap.draw("mymap.html")
    print df

def gridlines(g, bounds, height, width):
#    center_lat = (bounds['min_lat'] + bounds['max_lat']) * 1.0 / 2
#    center_lon = (bounds['min_lon'] + bounds['max_lon']) * 1.0 / 2
    lat_inc = (bounds['max_lat'] - bounds['min_lat']) * 1.0 / height
    lon_inc = (bounds['max_lon'] - bounds['min_lon']) * 1.0 / width
#    gmap = gmplot.GoogleMapPlotter(center_lat, center_lon, 12)
    g.grid(bounds['min_lat'] - lat_inc / 2, bounds['max_lat'] - lat_inc / 2, lat_inc, bounds['min_lon'] - lon_inc / 2, bounds['max_lon'] - lon_inc / 2, lon_inc)
    #gmap.draw("mymap.html")

def gm_scatter(geo, bounds, height, width, c, filename):
    center_lat = (bounds['min_lat'] + bounds['max_lat']) * 1.0 / 2
    center_lon = (bounds['min_lon'] + bounds['max_lon']) * 1.0 / 2
    gmap = gmplot.GoogleMapPlotter(center_lat, center_lon, 12)
#    gridlines(gmap, bounds, height, width)
    gmap.scatter(geo[:, 0], geo[:, 1], color = c, marker = False)
    gmap.draw(filename)

def gm_heat(geo, bounds):
    center_lat = (bounds['min_lat'] + bounds['max_lat']) * 1.0 / 2
    center_lon = (bounds['min_lon'] + bounds['max_lon']) * 1.0 / 2
    gmap = gmplot.GoogleMapPlotter(center_lat, center_lon, 12)
    gmap.heatmap(geo[:, 0], geo[:, 1])
    gmap.draw('mymap.html')

if __name__ == '__main__':
    '''
    collisions = read_collision_data()
    intersections, num_collisions = collision_intersections(collisions)
    collision_geo = google_api_geo(intersections, num_collisions)
    '''
    collision_geo = np.loadtxt('collision_geo2016.csv', delimiter = ',')
#    bbox = bounding_box(-122.516, 37.707, -122.356, 37.813)
    bbox = bounding_box(-122.463, 37.734, -122.383, 37.813)
    h = 7
    w = 7
    lat_grid, lon_grid = lat_lon_grid(bbox, h, w)
    collision_grid = grid(collision_geo, lat_grid, lon_grid)

    np.savetxt('collision_grid.csv', collision_grid.astype(int), delimiter = ',')

    collision_grid = filter_bounds(collision_grid, h, w)
#    effort = strava_api_segments(bbox, 8, 12)
    effort = np.loadtxt('segment_detail.csv', delimiter = ',')
    e_grid = grid(effort, lat_grid, lon_grid)
    effort_grid = effort_geo_to_grid(e_grid, effort)
    effort_grid = filter_bounds(effort_grid, h, w)
    collision_effort = combine_collision_effort(collision_grid, effort_grid)
    color_map(collision_effort, 'log_count_mean', bbox, lat_grid, lon_grid)
    gm_scatter(collision_geo, bbox, h, w, 'magenta', 'collision_map.html')
    gm_scatter(effort, bbox, h, w, 'blue', 'segment_map.html')
#    gm_heat(collision_geo, bbox)
