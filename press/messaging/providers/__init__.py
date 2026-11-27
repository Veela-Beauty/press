"""Local SMS providers Press sends through (owner 2026-11-27). One module per type, each with
send(settings, to_e164, text) -> (ok, detail). A new provider type is one more module and one more TYPES entry."""

from press.messaging.providers import smseg

_SENDERS = {"smseg": smseg.send}
TYPES = tuple(_SENDERS)


def send(provider_type, settings, to_e164, text):
	sender = _SENDERS.get(provider_type)
	if not sender:
		return False, f"No sender for provider type {provider_type}"
	return sender(settings, to_e164, text)
