from dataclasses import dataclass
import json
import logging
import os
import re
import time

import httpx
from tqdm import tqdm

logger = logging.getLogger(__name__)


@dataclass
class DiscordMessage:
    username: str
    message: str
    date_sent: str
    raw_data: dict


def _make_discord_search_request(
    server_id: str,
    offset: int = 0,
    attempt: int = 1,
    max_attempts=15,
) -> dict:
    try:
        # First, ensure we have a Bearer token.
        bearer_token = os.environ.get("DISCORD_BEARER_TOKEN")
        if not bearer_token:
            raise Exception("DISCORD_BEARER_TOKEN must be set in environ.")

        # TODO: Is it sufficient to actually just search for open.spotify.com? Might be
        # something better here.
        params = {"content": "https://open.spotify.com", "offset": offset}
        response = httpx.get(
            f"https://discord.com/api/v9/guilds/{server_id}/messages/search",
            params=params,
            headers={"Authorization": bearer_token},
        )
        response.raise_for_status()
        response_data = response.json()
        return response_data
    except httpx.HTTPStatusError:
        # If we're not getting a rate limiting exception, or we've exceeded our maximum
        # amount of retries, re-raise.
        if response.status_code != 429:
            raise
        if attempt == max_attempts:
            raise Exception("You tried too hard. Try less hard.")

        # Discord gives you a time to retry after if you get rate limited, but if
        # for some reason they don't, just use 5 seconds.
        try:
            error_details = response.json()
            retry_after = error_details["retry_after"]
        except:
            retry_after = 5
        logger.warning(
            f"Rate limited on attempt {attempt} for offset {offset}, "
            f"retrying after {retry_after} seconds..."
        )
        time.sleep(retry_after)
        return _make_discord_search_request(server_id, offset, attempt=attempt + 1)


def _extract_messages_from_discord_api_response(
    response_data: dict,
) -> list[DiscordMessage]:
    # For some odd reason, messages are represented as an array of one. Dunno why.
    return [
        DiscordMessage(
            username=message_datum[0]["author"]["username"],
            message=message_datum[0]["content"],
            date_sent=message_datum[0]["timestamp"],
            raw_data=message_datum[0],
        )
        for message_datum in response_data["messages"]
    ]


def retrieve_relevant_discord_messages(server_id) -> list[DiscordMessage]:
    # Do an initial response against the search API. This API is *not* documented,
    # and can only be used with a personal user bearer token, not a bot token. YMMV.
    initial_response_data = _make_discord_search_request(server_id)

    # Extract the initial set of messages.
    messages = _extract_messages_from_discord_api_response(initial_response_data)

    # Figure out how many more requests we'll need to make based on how many total
    # results there are, and then execute the requests and extract the messages.
    total_matches = initial_response_data["total_results"]
    offsets = range(25, total_matches, 25)
    for offset in tqdm(offsets):
        response_data = _make_discord_search_request(server_id, offset)
        messages += _extract_messages_from_discord_api_response(response_data)
    return messages
