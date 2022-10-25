"""Support for interface with a ArrisDCX960 Settopbox."""
import logging
import random
import voluptuous as vol
import time
import homeassistant.helpers.config_validation as cv

from homeassistant.components.media_player import MediaPlayerEntity, BrowseMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from .const import (
    API,
    DOMAIN,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_APP,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_CHANNEL,
    MEDIA_TYPE_TVSHOW,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_STOP,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_BROWSE_MEDIA,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_TV_SHOW,
    MEDIA_CLASS_EPISODE
)

from homeassistant.const import (
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)

from lghorizon import (
    LGHorizonBox,
    ONLINE_RUNNING,
    ONLINE_STANDBY,
    LGHorizonApi,
    LGHorizonRecordingShow,
    LGHorizonRecordingSingle,
    LGHorizonRecordingListSeasonShow,
    LGHorizonRecordingEpisode
    
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup platform"""
    players = []
    api = hass.data[DOMAIN][entry.entry_id][API]
    for box in api.settop_boxes.values():
        players.append(LGHorizonMediaPlayer(box, api))
    async_add_entities(players, True)


class LGHorizonMediaPlayer(MediaPlayerEntity):
    """The home assistant media player."""

    @property
    def unique_id(self):
        """Return the unique id."""
        return self.box_id

    @property
    def media_image_remotely_accessible(self):
        return True

    @property
    def device_class(self):
        return "tv"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._box.deviceId)
            },
            "name": self._box.deviceFriendlyName,
            "manufacturer": self._box.manufacturer or "unknown",
            "model": self._box.model or "unknown",
        }

    def __init__(self, box: LGHorizonBox, api: LGHorizonApi):
        """Init the media player."""
        self._box = box
        self.api = api
        self.box_id = box.deviceId
        self.box_name = box.deviceFriendlyName
        self._create_channel_map()

    def _create_channel_map(self):
        self._channels = {}
        for channel in self.api._channels.values():
            self._channels[channel.title] = channel.title

    async def async_added_to_hass(self):
        """Use lifecycle hooks."""

        def callback(box_id):
            self.schedule_update_ha_state(True)

        self._box.set_callback(callback)

    async def async_update(self):
        """Update the box."""
        pass

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.box_name

    @property
    def state(self):
        """Return the state of the player."""
        if self._box.state == ONLINE_RUNNING:
            if self._box.playing_info is not None and self._box.playing_info.paused:
                return STATE_PAUSED
            return STATE_PLAYING
        if self._box.state == ONLINE_STANDBY:
            return STATE_OFF
        return STATE_UNAVAILABLE

    @property
    def media_content_type(self):
        """Return the media type."""
        return MEDIA_TYPE_EPISODE

    @property
    def supported_features(self):
        """Return the supported features."""
        if self._box.playing_info.source_type == "app":
            return (
                SUPPORT_PLAY
                | SUPPORT_PAUSE
                | SUPPORT_STOP
                | SUPPORT_TURN_ON
                | SUPPORT_TURN_OFF
                | SUPPORT_SELECT_SOURCE
                | SUPPORT_PLAY_MEDIA
                | SUPPORT_BROWSE_MEDIA
            )
        return (
            SUPPORT_PLAY
            | SUPPORT_PAUSE
            | SUPPORT_STOP
            | SUPPORT_TURN_ON
            | SUPPORT_TURN_OFF
            | SUPPORT_SELECT_SOURCE
            | SUPPORT_NEXT_TRACK
            | SUPPORT_PREVIOUS_TRACK
            | SUPPORT_PLAY_MEDIA
            | SUPPORT_BROWSE_MEDIA
        )

    @property
    def available(self):
        """Return True if the device is available."""
        available = self._box.is_available()
        return available

    async def async_turn_on(self):
        """Turn the media player on."""
        self._box.turn_on()

    async def async_turn_off(self):
        """Turn the media player off."""
        self._box.turn_off()

    @property
    def media_image_url(self):
        """Return the media image URL."""
        image_url = self._box.playing_info.image
        if image_url is None:
            return None

        if self._box.playing_info.source_type == "linear":
            join_param = "?"
            if join_param in self._box.playing_info.image:
                join_param = "&"
            image_url = f"{image_url}{join_param}{str(random.randrange(1000000))}"
        return image_url
    @property
    def media_title(self):
        """Return the media title."""
        return self._box.playing_info.title

    @property
    def source(self):
        """Name of the current channel."""
        return self._box.playing_info.channel_title

    @property
    def source_list(self):
        """Return a list with available sources."""
        return [channel for channel in self._channels.keys()]

    async def async_select_source(self, source):
        """Select a new source."""
        self._box.set_channel(source)

    async def async_media_play(self):
        """Play selected box."""
        self._box.play()

    async def async_media_pause(self):
        """Pause the given box."""
        self._box.pause()

    async def async_media_stop(self):
        """Stop the given box."""
        self._box.stop()

    async def async_media_next_track(self):
        """Send next track command."""
        self._box.next_channel()

    async def async_media_previous_track(self):
        """Send previous track command."""
        self._box.previous_channel()

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        if media_type == MEDIA_TYPE_EPISODE:
            self._box.play_recording(media_id)
            pass
        elif media_type == MEDIA_TYPE_APP:
            self.api.select_source(media_id, self._box.deviceId)
        elif media_type == MEDIA_TYPE_CHANNEL:
            # media_id should only be a channel number
            try:
                cv.positive_int(media_id)
            except vol.Invalid:
                _LOGGER.error("Media ID must be positive integer")
                return
            if self._box.playing_info.source_type == "app":
                self._box._send_key_to_box("TV")
                time.sleep(1)

            for digit in media_id:
                self._box._send_key_to_box(f"{digit}")
        else:
            _LOGGER.error("Unsupported media type")

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "play_mode": self._box.playing_info.source_type,
            "channel": self._box.playing_info.channel_title,
            "title": self._box.playing_info.title,
            "image": self._box.playing_info.image,
        }

    @property
    def should_poll(self):
        return True

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        _LOGGER.debug(f"{media_content_type} - {media_content_id}")
        if media_content_type in [None, "main"]:
            main = BrowseMedia(
                title="Opnames",
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type="main",
                media_content_id="main",
                can_play=False,
                can_expand=True,
                children=[],
                children_media_class=MEDIA_CLASS_DIRECTORY,
            )
            recordings = await self.hass.async_add_executor_job(
                self.api.get_recordings
            )
            for recording in recordings:
                if type(recording) is LGHorizonRecordingListSeasonShow:
                    show: LGHorizonRecordingListSeasonShow = recording
                    show_media =  BrowseMedia(
                        title=show.title,
                        media_class=MEDIA_CLASS_TV_SHOW,
                        media_content_type=MEDIA_TYPE_TVSHOW,
                        media_content_id=show.showId,
                        can_play=False,
                        can_expand=True,
                        thumbnail=show.image,
                        children=[],
                        children_media_class=MEDIA_CLASS_DIRECTORY,
                    )
                    main.children.append(show_media)
                if type(recording) is LGHorizonRecordingSingle:
                    single: LGHorizonRecordingSingle = recording
                    single_media = BrowseMedia(
                        title=single.title,
                        media_class=MEDIA_CLASS_EPISODE,
                        media_content_type=MEDIA_TYPE_EPISODE,
                        media_content_id=single.id,
                        can_play=True,
                        can_expand=False,
                        thumbnail=single.image
                    )
                    main.children.append(single_media)
            return main
        elif media_content_type == MEDIA_TYPE_TVSHOW:
            episodes_data = await self.hass.async_add_executor_job(
                self.api.get_recording_show, media_content_id
            )
            children = []
            
            for episode_data in episodes_data:
                if type(episode_data) is LGHorizonRecordingEpisode:
                    episode_recording: LGHorizonRecordingEpisode = episode_data
                    planned: bool = episode_recording.recordingState == 'planned'
                    title=f"S{episode_recording.seasonNumber:02} E{episode_recording.episodeNumber:02}: {episode_recording.showTitle} - {episode_recording.episodeTitle}"
                    if planned:
                        title += " (planned)"
                    episode_media = BrowseMedia(
                        title=title,
                        media_class=MEDIA_CLASS_EPISODE,
                        media_content_type=MEDIA_TYPE_EPISODE,
                        media_content_id=episode_recording.episodeId,
                        can_play= not planned,
                        can_expand=False,
                        thumbnail=episode_recording.image
                    )
                    children.append(episode_media)
                elif type(episode_data) is LGHorizonRecordingShow:
                    show_recording: LGHorizonRecordingShow = episode_data
                    planned: bool = show_recording.recordingState == 'planned'
                    title = f"S{show_recording.seasonNumber:02} E{show_recording.episodeNumber:02}: {show_recording.showTitle}"
                    if planned:
                        title += " (planned)"
                    show_media = BrowseMedia(
                        title=title,
                        media_class=MEDIA_CLASS_EPISODE,
                        media_content_type=MEDIA_TYPE_EPISODE,
                        media_content_id=show_recording.episodeId,
                        can_play=not planned,
                        can_expand=False,
                        thumbnail=show_recording.image
                    )
                    children.append(show_media)
            show_container = BrowseMedia(
                title=episodes_data[0].showTitle,
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type=MEDIA_TYPE_TVSHOW,
                media_content_id=MEDIA_TYPE_TVSHOW,
                can_play=False,
                can_expand=False,
                children=children,
                children_media_class=MEDIA_CLASS_EPISODE,
                thumbnail=episodes_data[0].image
            )
            return show_container
        return None
                    
