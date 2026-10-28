PLUGIN_NAME = 'Ingenta Plugin'
DESCRIPTION = 'A plugin for importing back content from the Ingenta platform'
AUTHOR = 'Birkbeck Centre for Technology and Publishing'
VERSION = '0.1.1'
SHORT_NAME = 'ingenta'
MANAGER_URL = 'ingenta_index'
JANEWAY_VERSION = "1.7.0"

from utils import models


def install():
    new_plugin, created = models.Plugin.objects.get_or_create(
        name=SHORT_NAME,
        enabled=True,
        defaults={'version': VERSION},
    )

    if created:
        print('Plugin {0} installed.'.format(PLUGIN_NAME))
    else:
        print('Plugin {0} is already installed.'.format(PLUGIN_NAME))


def hook_registry():
    # On site load, the load function is run for each
    # installed plugin to generate
    # a list of hooks.
    return {}
