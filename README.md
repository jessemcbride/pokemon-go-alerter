This script records the visible Pokemon in a given area and then alerts Slack channels (Discord soon!) with their locations. The code is a mess, but shouldn't be for too long.

## Configuration

Rename `config.template.json` to `config.json` and fill out the required information. 

Your username and password need to be Pokemon Trainer Club credentials. Registration is a little tricky, but refreshing their registration page a lot or registering late at night (midnight EST) seems to help. In the future, this should support Google Auth as well.

Location can be GPS coordinates or an address.

Several Slack channels can be configured with different message delays like so:

```
"services": [
		{
			"name": "Slack Channel 1",
			"delay": 120,
			"webhook": "https://hooks.slack.com/services/something"
		},
		{
			"name": "Slack Channel 2",
			"delay": 60,
			"webhook": "https://hooks.slack.com/services/something_else"
		}
	]
```

The `delay` field is the minimum time in seconds between alerts. It's not exact, it's just a buffer to prevent your channel from being spammed.


