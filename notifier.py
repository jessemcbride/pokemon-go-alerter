import json
import requests
import time


COMMON = ['Pidgey', 'Weedle', 'Caterpie', 'Zubat', 'Rattata']

class Notifier(object):

    def __init__(self):
        self.services = json.load(open('config.json')).get('services')

        if self.services is None:
            print("[!] Warning: No services configured!")

    def notify(self, results):

        for i in range(len(results)):
            pokemon = results[i].split(' ')[0]

            if pokemon not in COMMON:
                results[i] = ":tada: " + results[i]
     
        results = {'text': "Pokemon scan results:\n\n %s" % ('\n'.join(results))}

        for service in self.services:

            if service.get('webhook'):
                r = requests.post(service.get('webhook'), data=json.dumps(results))
                service['last_message'] = time.time()
            else:
                print 'Service not yet supported.'
