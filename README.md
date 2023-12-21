# Hashtag Place ActivityPub server

Based on [django-activitypub-bot](https://github.com/christianp/django-activitypub-bot), this is a server that allows the seamless following of ActivityPub hashtags as bot accounts, for smaller instances that may not see these posts, or implementations that do not allow for following hashtags directly. The "main" instance is hosted at [Hashtag.place](https://hashtag.place)

## Installation

Assumptions:

* You have an existing web server serving a site under a domain name that you'd like to use for an ActivityPub actor, with root (superuser) access.
* These instructions are for a server running Ubuntu Linux, with the nginx web server.

You need Python 3.9 or later to run this.

Clone this repository (I cloned it into `/srv/activitypub`, so that's what these instructions will use), and install the requirements, with 

```
pip install -r requirements.txt
```

It's a good idea to set up a [virtual environment](https://docs.python.org/3/library/venv.html) to do this in.
I set up a virtual environment in `/srv/activitypub/venv`.

Make sure you activate the virtual environment after creating it!

Copy `activitypub_bot/settings.py.dist` to `activitypub_bot/settings.py`, and fill in the settings, following the instructions in that file.

Copy the files in `systemd_services` to `/etc/systemd/system`, and enable them:

Copy `gunicorn.conf.py.dist` to `gunicorn.conf.py` and change it if you used different paths for the repository or the virtual environment.

Run `python manage.py migrate` to set up the database.

Enable the services:

```
systemctl enable activitypub_huey.service activitypub.service activitypub.socket
```

For each domain you want to run ActivityPub on, the server needs to handle requests to the URL `/.well-known/webfinger` and anything under `/activitypub`.
(You can replace `/activitypub` with something else if you want).

Add the following rules to each nginx config that handles domains you want to run ActivityPub on:

```
server {
    # ... your existing config

    location ~ /activitypub/static {
        rewrite ^/activitypub/static/(.*)$ /$1 break;
        root /srv/activitypub/public/static;
    }
    location ~ /activitypub {
        include proxy_params;
        proxy_pass http://unix:/run/activitypub.sock;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
    location = /.well-known/webfinger {
        include proxy_params;
        proxy_pass http://unix:/run/activitypub.sock;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

Reload nginx's config:

```
systemctl reload nginx
```

It's useful to create superuser login details for the admin interface:

```
python manage.py createsuperuser
```

If everything is set up properly, `https://{DOMAIN}/activitypub/admin` will show you the Django admin login screen.

## Inbox handlers

When an ActivityPub message is received, it's handled by a series of subclasses of `bot.inbox.AbstractInboxHandler`.

For an activity with `Type: "ActivityType"`, the corresponding method `handle_ActivityType(activity)` on each inbox handler will be called.

Django apps can register a new inbox handler class with `bot.inbox.register_inbox_handler(cls, spec)`. 
`should_handle` is either a callable of the form `spec(actor, activity)` which should return a boolean dictating whether the class should handle this activity received by this actor, or it should be a dictionary with keys `username` and `domain` specifying the usernames, domains, or both, whose inboxes this class should handle.
If `should_handle` is not given, then the handler is called for every activity.

There is a built-in inbox handler, `bot.inbox.InboxHandler`, which manages `Follow` and `Like` activities.

You could define an inbox handler which sends you an email whenever a `Mention` activity is received.

## Help with ActivityPub

The specs are good!

The [ActivityPub protocol specification](https://www.w3.org/TR/activitypub/) gives a description of how interactions work.

The [Activity Streams Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/) 
