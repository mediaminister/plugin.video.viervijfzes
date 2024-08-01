# -*- coding: utf-8 -*-
""" Catalog module """

from __future__ import absolute_import, division, unicode_literals

import logging

from resources.lib import kodiutils
from resources.lib.kodiutils import TitleItem
from resources.lib.modules.menu import Menu
from resources.lib.viervijfzes.auth import AuthApi
from resources.lib.viervijfzes.content import CACHE_PREVENT, ContentApi, UnavailableException

_LOGGER = logging.getLogger(__name__)


class Catalog:
    """ Menu code related to the catalog """

    def __init__(self):
        """ Initialise object """
        self._auth = AuthApi(kodiutils.get_setting('username'), kodiutils.get_setting('password'), kodiutils.get_tokens_path())
        self._api = ContentApi(self._auth, cache_path=kodiutils.get_cache_path())

    def show_catalog(self):
        """ Show all the programs of all channels """
        try:
            items = self._api.get_programs()
        except Exception as ex:
            kodiutils.notification(message=str(ex))
            raise

        listing = [Menu.generate_titleitem(item) for item in items]

        # Sort items by title
        # Used for A-Z listing or when movies and episodes are mixed.
        kodiutils.show_listing(listing, 30003, content='tvshows', sort='title')

    def show_catalog_channel(self, channel):
        """ Show the programs of a specific channel
        :type channel: str
        """
        try:
            items = self._api.get_programs(channel=channel)
        except Exception as ex:
            kodiutils.notification(message=str(ex))
            raise

        listing = []
        for item in items:
            listing.append(Menu.generate_titleitem(item))

        # Sort items by title
        # Used for A-Z listing or when movies and episodes are mixed.
        kodiutils.show_listing(listing, 30003, content='tvshows', sort='title')

    def show_program(self, program_uuid):
        """ Show a program from the catalog
        :type program_id: str
         """
        try:
            program = self._api.get_program_by_uuid(program_uuid, cache=CACHE_PREVENT)  # Use CACHE_PREVENT since we want fresh data
        except UnavailableException:
            kodiutils.ok_dialog(message=kodiutils.localize(30717))  # This program is not available in the catalogue.
            kodiutils.end_of_directory()
            return

        if not program.seasons:
            kodiutils.ok_dialog(message=kodiutils.localize(30717))  # This program is not available in the catalogue.
            kodiutils.end_of_directory()
            return

        # Go directly to the season when we have only one season and no clips
        if not program.clips and len(program.seasons) == 1:
            self.show_season(list(program.seasons.values())[0].uuid)
            return

        listing = []

        # Add the seasons
        for season in list(program.seasons.values()):
            listing.append(
                TitleItem(
                    title=season.title,
                    path=kodiutils.url_for('show_catalog_program_season', program=program_uuid, season=season.uuid),
                    art_dict={
                        'fanart': program.fanart,
                        'poster': program.poster,
                        'landscape': program.thumb,
                    },
                    info_dict={
                        'tvshowtitle': program.title,
                        'title': season.title,
                        'plot': season.description or program.description,
                        'set': program.title,
                    }
                )
            )

        # Add Clips
        if program.clips:
            listing.append(
                TitleItem(
                    title=kodiutils.localize(30059, program=program.title),  # Clips for {program}
                    path=kodiutils.url_for('show_catalog_program_clips', program=program_uuid),
                    art_dict={
                        'fanart': program.fanart,
                        'poster': program.poster,
                        'landscape': program.thumb,
                    },
                    info_dict={
                        'tvshowtitle': program.title,
                        'title': kodiutils.localize(30059, program=program.title),  # Clips for {program}
                        'plot': kodiutils.localize(30060, program=program.title),  # Watch short clips of {program}
                        'set': program.title,
                    }
                )
            )

        # Sort by label. Some programs return seasons unordered.
        kodiutils.show_listing(listing, 30003, content='tvshows')

    def show_season(self, season_uuid):
        """ Show the episodes of a season from the catalog
        :type season_uuid: str
        """
        try:
            episodes = self._api.get_episodes(season_uuid)
        except UnavailableException:
            kodiutils.ok_dialog(message=kodiutils.localize(30717))  # This program is not available in the catalogue.
            kodiutils.end_of_directory()
            return

        listing = [Menu.generate_titleitem(episode) for episode in episodes]

        # Sort by episode number by default. Takes seasons into account.
        kodiutils.show_listing(listing, 30003, content='episodes', sort=['episode', 'duration'])

    def show_program_clips(self, program_id):
        """ Show the clips of a program from the catalog
        :type program_id: str
        """
        try:
            # We need to query the backend, since we don't cache clips.
            program = self._api.get_program(program_id, extract_clips=True, cache=CACHE_PREVENT)
        except UnavailableException:
            kodiutils.ok_dialog(message=kodiutils.localize(30717))  # This program is not available in the catalogue.
            kodiutils.end_of_directory()
            return

        listing = [Menu.generate_titleitem(episode) for episode in program.clips]

        # Sort like we get our results back.
        kodiutils.show_listing(listing, 30003, content='episodes')

    def show_categories(self):
        """ Shows the categories """
        categories = self._api.get_categories()

        listing = []
        for category in categories:
            listing.append(TitleItem(title=category.title,
                                     path=kodiutils.url_for('show_category', category=category.uuid),
                                     info_dict={
                                         'title': category.title,
                                     }))

        kodiutils.show_listing(listing, 30003, sort=['title'])

    def show_category(self, uuid):
        """ Shows a category """
        programs = self._api.get_programs(category=uuid)

        listing = [
            Menu.generate_titleitem(program) for program in programs
        ]

        kodiutils.show_listing(listing, 30003, content='tvshows')

    def show_recommendations(self):
        """ Shows the recommendations """
        listing = []
        recommendations = self._api.get_page('home')
        for swimlane in recommendations:
            listing.append(TitleItem(title=swimlane.title,
                                     path=kodiutils.url_for('show_recommendations_category', category=swimlane.index),
                                     info_dict={
                                         'title': swimlane.title,
                                     }))

        kodiutils.show_listing(listing, 30005, content='tvshows')

    def show_recommendations_category(self, index):
        """ Shows a category of the recommendations """
        videos, programs = self._api.get_swimlane('home', index)

        listing = []
        for video in videos:
            title_item = Menu.generate_titleitem(video)
            if video.program_title:
                title_item.info_dict['title'] = video.program_title + ' - ' + title_item.title
            listing.append(title_item)

        for program in programs:
            listing.append(Menu.generate_titleitem(program))

        kodiutils.show_listing(listing, 30005, content='tvshows')

    def show_mylist(self):
        """ Show the programs of My List """
        mylist = self._api.get_mylist()

        listing = [Menu.generate_titleitem(item) for item in mylist]

        # Sort items by title
        # Used for A-Z listing or when movies and episodes are mixed.
        kodiutils.show_listing(listing, 30011, content='tvshows', sort='title')

    def mylist_add(self, uuid):
        """ Add a program to My List """
        if not uuid:
            kodiutils.end_of_directory()
            return

        self._api.mylist_add(uuid)

        kodiutils.end_of_directory()

    def mylist_del(self, uuid):
        """ Remove a program from My List """
        if not uuid:
            kodiutils.end_of_directory()
            return

        self._api.mylist_del(uuid)

        kodiutils.end_of_directory()
