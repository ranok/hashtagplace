from   . import activitystreams
from   .send_signed_message import signed_post
from   django.utils import dateparse
from   huey.contrib.djhuey import task, periodic_task
from huey import crontab
import json

@periodic_task(crontab(day='*/3'))
def purge_unfollowed():
    accts = LocalActor.objects.all()
    for a in accts:
        if len(a.followers.all()) == 0:
            a.delete()

@periodic_task(crontab(minute='*/5'))
def check_for_new_posts():
    from .models import LocalActor
    import requests
    print("Checking for new posts!")
    accts = LocalActor.objects.all()
    search_domain = "https://mastodon.social/api/v1/timelines/tag/"
    for a in accts:
        if len(a.followers.all()) == 0:
            continue
        print(f"Handling {a.username}!")
        uris = set()
        if a.since_id == '':
            res = requests.get(search_domain + a.username + '?limit=5').json()
        else:
            res = requests.get(search_domain + a.username + '?since_id=' + a.since_id).json()
        if len(res) == 0:
            continue
        a.since_id = res[0].get('id', '')
        a.save()
        for status in res:
            uris.add(status.get('uri'))
        uris.add(None)
        uris.remove(None)
        print(f"Got {len(uris)} to announce!")
        for uri in list(uris):
            a.create_announce(uri)

@task()
def update_profile(actor):
    actor.update_profile()

@task()
def send_message(inbox_url, message, private_key_pem, public_key_url):
    print(f"Sending to {inbox_url}:\n{json.dumps(message,indent=4)}")
    signed_post(inbox_url, private_key_pem, public_key_url, body = json.dumps(message))

@task()
def add_follower(actor, follower_url, accept_message):
    from .models import RemoteActor
    remote_actor = RemoteActor.objects.get_by_url(follower_url)
    actor.followers.add(remote_actor)

    actor.send_signed_message(remote_actor.get_inbox_url(), accept_message)

@task()
def remove_follower(actor, follower_url):
    from .models import RemoteActor
    remote_actor = RemoteActor.objects.get_by_url(follower_url)
    actor.followers.remove(remote_actor)

@task()
def add_like(actor, activity):
    from .models import Note, RemoteActor
    note = Note.objects.get_by_absolute_url(activity['object'])
    remote_actor = RemoteActor.objects.get_by_url(activity['actor'])
    note.likes.add(remote_actor)

@task()
def remove_like(actor, activity):
    from .models import Note, RemoteActor
    note = Note.objects.get_by_absolute_url(activity['object']['object'])
    remote_actor = RemoteActor.objects.get_by_url(activity['actor'])
    note.likes.remove(remote_actor)

@task()
def add_announce(actor, activity):
    from .models import Note, RemoteActor
    note = Note.objects.get_by_absolute_url(activity['object'])
    remote_actor = RemoteActor.objects.get_by_url(activity['actor'])
    note.announces.add(remote_actor)

@task()
def remove_announce(actor, activity):
    from .models import Note, RemoteActor
    note = Note.objects.get_by_absolute_url(activity['object']['object'])
    remote_actor = RemoteActor.objects.get_by_url(activity['actor'])
    note.announces.remove(remote_actor)

@task()
def save_mention(recipient, activity):
    from .models import Note, RemoteActor

    remote_actor_url = activity['actor']
    remote_actor = RemoteActor.objects.get_by_url(remote_actor_url)
    note_json = activity['object']

    try:
        in_reply_to = Note.objects.get_by_absolute_url(note_json.get('inReplyTo'))
    except Exception:
        in_reply_to = None

    note = Note.objects.create(
        remote_actor = remote_actor,
        data = note_json,
        published_date = dateparse.parse_datetime(note_json.get('published')),
        public = activitystreams.PUBLIC in note_json.get('to',[]),
        in_reply_to = in_reply_to
    )

    note.mentions.add(recipient)
