import click
import logging

from tqdm import tqdm

from discord import retrieve_relevant_discord_messages
from spotify import SpotifyApi, get_uri_from_discord_message

logger = logging.getLogger(__name__)


@click.command()
@click.option("--server-id", default="689619583841337505")
@click.option("--playlist-id", default="1o1LieydFE80e9PoCMBmt0")
def sync_discord_spotify_links_to_playlist(server_id: str, playlist_id: str):
    # TODO: Allow date range, using DISCORD_EPOCH.
    logger.info("Retrieving messages with Spotify links from Discord...")
    discord_messages = retrieve_relevant_discord_messages(server_id)

    logger.info(f"{len(discord_messages)} possibly relevant messages retrieved.")
    logger.info("Extracting URIs from Discord messages...")
    api = SpotifyApi()
    spotify_uris_from_discord = []
    for discord_message in discord_messages:
        try:
            uri = get_uri_from_discord_message(discord_message, api)
            spotify_uris_from_discord.append(uri)
        except:
            logger.warning(f'Could not parse {discord_message}.')

    logger.info(f"{len(spotify_uris_from_discord)} Spotify URIs extracted.")
    logger.info(f"Retrieving existing tracks from playlist {playlist_id}...")
    existing_track_uris = api.get_playlist_item_uris(playlist_id)

    # Figure out what items need to be added.
    items_to_add = list(set(spotify_uris_from_discord) - set(existing_track_uris))
    logger.info(f"Adding {len(items_to_add)} new tracks.")

    # Add them.
    chunk_size = 25
    chunked_start_indices = range(0, len(items_to_add), chunk_size)
    for start_index in tqdm(chunked_start_indices):
        end_index = start_index + chunk_size - 1
        api.add_playlist_items(playlist_id, items_to_add[start_index:end_index])


if __name__ == "__main__":
    sync_discord_spotify_links_to_playlist()
