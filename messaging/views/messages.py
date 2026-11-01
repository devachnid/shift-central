"""Messages: inbox, one message, send, sent (spec 5, section 5)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from messaging.forms import MessageForm
from messaging.services import messages as svc
from people.services import access


@login_required
def inbox(request):
    return render(request, "messaging/inbox.html", {"page_title": "Messages", "rows": svc.inbox(request.user)})


@login_required
def detail(request, pk):
    message, receipt = svc.open_message(request.user, pk)
    return render(request, "messaging/message.html", {"page_title": "Message", "message": message, "receipt": receipt})


@login_required
@access.manager_required
def new(request):
    initial = {}
    person = request.GET.get("person", "")
    if person.isascii() and person.isdigit():
        initial["people"] = [int(person)]
    form = MessageForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            message = svc.send(request.user, d["subject"], d["body"], [p.pk for p in d["people"]],
                               [t.pk for t in d["teams"]], d["everyone"], base_url=request.build_absolute_uri("/"))
            return render(request, "messaging/send_dialog.html", {"form": None, "sent_to": message.recipients.count()})
        except svc.MessageError as e:
            form.add_error(None, e.message)
    return render(request, "messaging/send_dialog.html", {"form": form, "sent_to": None})


@login_required
@access.manager_required
def sent(request):
    return render(request, "messaging/sent.html", {"page_title": "Sent messages", "rows": svc.sent(request.user)})
