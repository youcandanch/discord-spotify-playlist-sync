import logging
import os
import re
from urllib.parse import urlparse

import httpx

from discord import DiscordMessage

logger = logging.getLogger(__name__)


class SpotifyApi:
    def __init__(self):
        bearer_token = os.environ.get("SPOTIFY_BEARER_TOKEN")
        if bearer_token is None:
            raise Exception("SPOTIFY_BEARER_TOKEN must be set in environ.")
        self.client = httpx.Client(
            base_url="https://api.spotify.com/v1",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )

    def _get(self, path, params={}) -> dict:
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, data: dict) -> dict:
        response = self.client.post(path, json=data)
        response.raise_for_status()
        return response.json()

    def add_playlist_items(self, playlist_id: str, spotify_uris: list[str]):
        return self._post(f"/playlists/{playlist_id}/tracks", {"uris": spotify_uris})

    def get_playlist_item_uris(self, playlist_id: str) -> list[str]:
        response_data = self._get(
            f"/playlists/{playlist_id}/tracks",
            {
                "limit": 50,
            },
        )
        uris = [item["track"]["uri"] for item in response_data["items"]]
        next_url = response_data.get("next")
        while next_url is not None:
            response = self.client.get(next_url)
            response_data = response.json()
            uris += [item["track"]["uri"] for item in response_data["items"]]
            next_url = response_data.get("next")
        return uris

    def get_first_track_uri_from_album(self, album_id: str):
        response = self._get(f"/albums/{album_id}/tracks")
        first_track = response["items"][0]
        return first_track["uri"]


def get_uri_from_discord_message(discord_message: DiscordMessage, api: SpotifyApi):
    # Extract the spotify URL from the message and break it into parts. We only
    # care about the path.
    url = re.search("(?P<url>https?://[^\s]+)", discord_message.message).group("url")
    _, _, path, _, _, _ = urlparse(url)

    # URLs have a leading slash, then the type of link it is, then the ID itself.
    _, link_type, spotify_id = path.split("/")

    # Ensure there's only alphanumeric characters in the IDs, getting rid of stuff like
    # commas and whatnot.
    spotify_id = re.sub("[^0-9a-zA-Z]+", "", spotify_id)
    if link_type == "track":
        return f"spotify:track:{spotify_id}"
    if link_type == "album":
        # Retrieve the first track from an album as the URI.
        # TODO: Consider doing it by popularity? That'd require multiple
        # requests, one to get the list of tracks, then hitting the tracks/ endpoint
        # since popularity isn't available just on the album/tracks endpoint.
        return api.get_first_track_uri_from_album(spotify_id)

    # We only process tracks and albums right now. Ignore everything else.
    logger.warning(f"Unsupported Spotify Link type: {path}")
