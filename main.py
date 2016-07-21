from geopy.geocoders import GoogleV3
from google.protobuf.internal import encoder
from notifier import Notifier
import pokemon_pb2
from s2sphere import *
from util import f2i

from datetime import datetime
from random import randint

import argparse
import json
import requests
import re
import time

from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

API_URL = 'https://pgorelease.nianticlabs.com/plfe/rpc'
LOGIN_URL = 'https://sso.pokemon.com/sso/login?service=https%3A%2F%2Fsso.pokemon.com%2Fsso%2Foauth2.0%2FcallbackAuthorize'
LOGIN_OAUTH = 'https://sso.pokemon.com/sso/oauth2.0/accessToken'

DEBUG = False
COORDS_LATITUDE = 0
COORDS_LONGITUDE = 0
COORDS_ALTITUDE = 0
FLOAT_LAT = 0
FLOAT_LONG = 0

notifier = Notifier()

session = requests.session()
session.headers.update({'User-Agent': 'Niantic App'})
session.verify = False

def encode(cellid):
    output = []
    encoder._VarintEncoder()(output.append, cellid)
    return ''.join(output)

def get_neighbors():
    origin = CellId.from_lat_lng(LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)).parent(15)
    walk = [origin.id()]

    # 10 before and 10 after
    next = origin.next()
    prev = origin.prev()
    
    for i in range(10):
        walk.append(prev.id())
        walk.append(next.id())
        next = next.next()
        prev = prev.prev()
    
    return walk

def set_location(location_name):
    geolocator = GoogleV3()
    loc = geolocator.geocode(location_name)

    print('[!] Your given location: {}'.format(loc.address.encode('utf-8')))
    print('[!] lat/long/alt: {} {} {}'.format(loc.latitude, loc.longitude, loc.altitude))
    set_location_coords(loc.latitude, loc.longitude, loc.altitude)

def set_location_coords(latitude, longitude, altitude):
    global COORDS_LATITUDE, COORDS_LONGITUDE, COORDS_ALTITUDE
    global FLOAT_LAT, FLOAT_LONG
    FLOAT_LAT = latitude
    FLOAT_LONG = longitude
    COORDS_LATITUDE = f2i(latitude) # 0x4042bd7c00000000 # f2i(lat)
    COORDS_LONGITUDE = f2i(longitude) # 0xc05e8aae40000000 #f2i(long)
    COORDS_ALTITUDE = f2i(altitude)

def get_location_coords():
    return (COORDS_LATITUDE, COORDS_LONGITUDE, COORDS_ALTITUDE)

def api_req(api_endpoint, access_token, *mehs, **kw):
    try:
        p_req = pokemon_pb2.RequestEnvelop()
        p_req.rpc_id = 1469378659230941192

        p_req.unknown1 = 2

        p_req.latitude, p_req.longitude, p_req.altitude = get_location_coords()

        p_req.unknown12 = 989

        if 'useauth' not in kw or not kw['useauth']:
            p_req.auth.provider = 'ptc'
            p_req.auth.token.contents = access_token
            p_req.auth.token.unknown13 = 14
        else:
            p_req.unknown11.unknown71 = kw['useauth'].unknown71
            p_req.unknown11.unknown72 = kw['useauth'].unknown72
            p_req.unknown11.unknown73 = kw['useauth'].unknown73

        for meh in mehs:
            p_req.MergeFrom(meh)

        protobuf = p_req.SerializeToString()

        r = session.post(api_endpoint, data=protobuf, verify=False)

        p_ret = pokemon_pb2.ResponseEnvelop()
        p_ret.ParseFromString(r.content)

        if DEBUG:
            print("REQUEST:")
            print(p_req)
            print("Response:")
            print(p_ret)
            print("\n\n")

            print("Sleeping for 2 seconds to get around rate-limit.")
        
        time.sleep(2)
        return p_ret
    except Exception, e:
        if DEBUG:
            print(e)
        return None

def get_profile(access_token, api, useauth, *reqq):
    req = pokemon_pb2.RequestEnvelop()

    req1 = req.requests.add()
    req1.type = 2
    if len(reqq) >= 1:
        req1.MergeFrom(reqq[0])

    req2 = req.requests.add()
    req2.type = 126
    if len(reqq) >= 2:
        req2.MergeFrom(reqq[1])

    req3 = req.requests.add()
    req3.type = 4
    if len(reqq) >= 3:
        req3.MergeFrom(reqq[2])

    req4 = req.requests.add()
    req4.type = 129
    if len(reqq) >= 4:
        req4.MergeFrom(reqq[3])

    req5 = req.requests.add()
    req5.type = 5
    if len(reqq) >= 5:
        req5.MergeFrom(reqq[4])

    return api_req(api, access_token, req, useauth = useauth)

def get_api_endpoint(access_token, api = API_URL):
    p_ret = get_profile(access_token, api, None)
    try:
        return ('https://%s/rpc' % p_ret.api_url)
    except:
        return None

def login_ptc(username, password):
    print('[!] Login for: {}'.format(username))
    head = {'User-Agent': 'niantic'}
    r = session.get(LOGIN_URL, headers=head)
    
    try:
        jdata = json.loads(r.content)
    except:
        return None

    data = {
        'lt': jdata['lt'],
        'execution': jdata['execution'],
        '_eventId': 'submit',
        'username': username,
        'password': password,
    }
    r1 = session.post(LOGIN_URL, data=data, headers=head)

    ticket = None
    try:
        ticket = re.sub('.*ticket=', '', r1.history[0].headers['Location'])
    except Exception as e:
        if DEBUG:
            print(r1.json()['errors'][0])
        return None

    data1 = {
        'client_id': 'mobile-app_pokemon-go',
        'redirect_uri': 'https://www.nianticlabs.com/pokemongo/error',
        'client_secret': 'w8ScCUXJQc6kXKw8FiOhd8Fixzht18Dq3PEVkUCP5ZPxtgyWsbTvWHFLm2wNY0JR',
        'grant_type': 'refresh_token',
        'code': ticket,
    }
    r2 = session.post(LOGIN_OAUTH, data=data1)
    access_token = re.sub('&expires.*', '', r2.content)
    access_token = re.sub('.*access_token=', '', access_token)
    return access_token

def heartbeat(api_endpoint, access_token, response):
    m4 = pokemon_pb2.RequestEnvelop.Requests()
    m = pokemon_pb2.RequestEnvelop.MessageSingleInt()
    m.f1 = int(time.time() * 1000)
    m4.message = m.SerializeToString()
    m5 = pokemon_pb2.RequestEnvelop.Requests()
    m = pokemon_pb2.RequestEnvelop.MessageSingleString()
    m.bytes = "05daf51635c82611d1aac95c0b051d3ec088a930"
    m5.message = m.SerializeToString()

    walk = sorted(get_neighbors())

    m1 = pokemon_pb2.RequestEnvelop.Requests()
    m1.type = 106
    m = pokemon_pb2.RequestEnvelop.MessageQuad()
    m.f1 = ''.join(map(encode, walk))
    m.f2 = "\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000"
    m.lat = COORDS_LATITUDE
    m.long = COORDS_LONGITUDE
    m1.message = m.SerializeToString()

    response = get_profile(
        access_token,
        api_endpoint,
        response.unknown7,
        m1,
        pokemon_pb2.RequestEnvelop.Requests(),
        m4,
        pokemon_pb2.RequestEnvelop.Requests(),
        m5
    )

    try:
        payload = response.payload[0]
    except:
        print '[-] Failed to connect.'
        return None

    hb = pokemon_pb2.ResponseEnvelop.HeartbeatPayload()
    hb.ParseFromString(payload)
    return hb

def main():
    try:
        config = json.load(open('config.json'))
    except Exception as e:
        print("[-] Couldn't open config.json. Does it exist / does it contain valid JSON?")
        return

    set_location(config['location'])

    access_token = login_ptc(config['username'], config['password']) 

    while access_token is None:
        print('[-] Unable to authenticate with Pokemon Trainer Club credentials. Retrying...')
        time.sleep(randint(2, 12))

        # Start a new session
        global session
        session = requests.session()
        session.headers.update({'User-Agent': 'Niantic App'})
        session.verify = False
        access_token = login_ptc(config['username'], config['password'])

    print('[+] RPC Session Token: {} ...'.format(access_token[:25]))

    api_endpoint = get_api_endpoint(access_token)

    while api_endpoint is None:
        api_endpoint = get_api_endpoint(access_token)
        print('[-] RPC server offline. Retrying...')

    print('[+] Received API endpoint: {}'.format(api_endpoint))
    scan(access_token, api_endpoint)

def scan(access_token, api_endpoint):
    try: 
        pokemons = json.load(open('data/pokemon.json'))
    except:
        print("[-] Couldn't open data/pokemon.json. Does it exist?")
        return

    response = get_profile(access_token, api_endpoint, None)
    origin = LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)

    while response is None:
        print("[-] Failed to connect, retrying...")
        time.sleep(randint(2, 12))
        main()
        return

    while True:
        print "[!] Scanning for nearby Pokemon..."
       
        poke_list = []

        original_lat = FLOAT_LAT
        original_long = FLOAT_LONG
        parent = CellId.from_lat_lng(LatLng.from_degrees(FLOAT_LAT, FLOAT_LONG)).parent(15)

        h = heartbeat(api_endpoint, access_token, response)

        if h is None:
            main()
            break

        hs = [h]
        seen = set([])

        for child in parent.children():
            latlng = LatLng.from_point(Cell(child).get_center())
            set_location_coords(latlng.lat().degrees, latlng.lng().degrees, 0)
            hs.append(heartbeat(api_endpoint, access_token, response))

        set_location_coords(original_lat, original_long, 0)

        visible = []

        for hh in hs:

            try:
                for cell in hh.cells:
                    for wild in cell.WildPokemon:
                        hash = wild.SpawnPointId + ':' + str(wild.pokemon.PokemonId)
                        if hash not in seen:
                            visible.append(wild)
                            seen.add(hash)
            except: 
                # hh no cells
                pass

        for cell in h.cells:
            if cell.NearbyPokemon:
                other = LatLng.from_point(Cell(CellId(cell.S2CellId)).get_center())
                diff = other - origin

                difflat = diff.lat().degrees
                difflng = diff.lng().degrees
                direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '')  + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')
                # print("Within one step of %s (%sm %s from you):" % (other, int(origin.get_distance(other).radians * 6366468.241830914), direction))
                # for poke in cell.NearbyPokemon:
                #    print('(%s) %s' % (poke.PokedexNumber, pokemons[poke.PokedexNumber - 1]['Name']))

        for poke in visible:
            other = LatLng.from_degrees(poke.Latitude, poke.Longitude)
            diff = other - origin

            difflat = diff.lat().degrees
            difflng = diff.lng().degrees
            direction = (('N' if difflat >= 0 else 'S') if abs(difflat) > 1e-4 else '')  + (('E' if difflng >= 0 else 'W') if abs(difflng) > 1e-4 else '')

            # print("(%s) %s is visible at (%s, %s) for %s seconds (%sm %s from you)" % (poke.pokemon.PokemonId, pokemons[poke.pokemon.PokemonId - 1]['Name'], poke.Latitude, poke.Longitude, poke.TimeTillHiddenMs / 1000, int(origin.get_distance(other).radians * 6366468.241830914), direction))
            
            result = "%s visible at <https://www.google.com/maps?q=%s,%s|(%s, %s)>" % (pokemons[poke.pokemon.PokemonId - 1]['Name'], poke.Latitude, poke.Longitude, poke.Latitude, poke.Longitude)
            poke_list.append(result)

        payload = {'text': "Pokemon scan results:\n\n %s" % ('\n'.join(poke_list))}

        notifier.notify(poke_list)
        time.sleep(120)

if __name__ == '__main__':
    main()
