###################################################################
# Copyright 2013-2015 All Rights Reserved
# Authors: The Paradrop Team
###################################################################

"""
Functions associated with deploying and cleaning up docker containers.
"""

from pdtools.lib.output import out
import docker
import json
import os
import subprocess

from paradrop.lib import settings
from pdtools.lib import nexus


DOCKER_CONF = """
# Docker systemd configuration
#
# This configuration file was automatically generated by Paradrop.  Any changes
# will be overwritten on startup.

# Tell docker not to start containers automatically on startup.
DOCKER_OPTIONS="--restart=false"
"""


def writeDockerConfig():
    """
    Write options to Docker configuration.

    Mainly, we want to tell Docker not to start containers automatically on
    system boot.
    """
    # First we have to find the configuration file.  On Snappy, it should be in
    # "/var/lib/apps/docker/{version}/etc/docker.conf", but version could
    # change.
    path = "/var/lib/apps/docker"
    if not os.path.exists(path):
        out.warn('No directory "{}" found'.format(path))
        return False

    written = False
    for d in os.listdir(path):
        finalPath = os.path.join(path, d, "etc/docker.conf")
        if not os.path.exists(finalPath):
            continue

        try:
            with open(finalPath, "w") as output:
                output.write(DOCKER_CONF)
            written = True
        except Exception as e:
            out.warn('Error writing to {}: {}'.format(finalPath, str(e)))

    if not written:
        out.warn('Could not write docker configuration.')
    return written


def startChute(update):
    """
    Build and deploy a docker container based on the passed in update.

    :param update: The update object containing information about the chute.
    :type update: obj
    :returns: None
    """
    out.info('Attempting to start new Chute %s \n' % (update.name))

    repo = update.name + ":latest"
    dockerfile = update.dockerfile
    name = update.name

    c = docker.Client(base_url="unix://var/run/docker.sock", version='auto')

    host_config = build_host_config(update, c)

    #Get Id's of current images for comparison upon failure
    validImages = c.images(quiet=True, all=False)
    validContainers = c.containers(quiet=True, all=True)

    buildFailed = False
    for line in c.build(rm=True, tag=repo, fileobj=dockerfile):

        #if we encountered an error make note of it
        if 'errorDetail' in line:
            buildFailed = True

        for key, value in json.loads(line).iteritems():
            if isinstance(value, dict):
                continue
            else:
                msg = str(value).rstrip()
                update.progress(msg)

    #If we failed to build skip creating and starting clean up and fail
    if buildFailed:
        cleanUpDocker(validImages, validContainers)
        raise Exception("Building docker image failed; check your Dockerfile for errors.")

    # Set environment variables for the new container.
    # PARADROP_ROUTER_ID can be used to change application behavior based on
    # what router it is running on.
    environment = prepare_environment(update)

    try:
        container = c.create_container(
            image=repo, name=name, host_config=host_config,
            environment=environment
        )
        c.start(container.get('Id'))
        out.info("Successfully started chute with Id: %s\n" % (str(container.get('Id'))))
    except Exception as e:
        cleanUpDocker(validImages, validContainers)
        raise e

    setup_net_interfaces(update)

def removeChute(update):
    """
    Remove a docker container and the image it was built on based on the passed in update.

    :param update: The update object containing information about the chute.
    :type update: obj
    :returns: None
    """
    out.info('Attempting to remove chute %s\n' % (update.name))
    c = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
    repo = update.name + ":latest"
    name = update.name
    try:
        c.remove_container(container=name, force=True)
        c.remove_image(image=repo)
    except Exception as e:
        #TODO: Might want to notify ourselves we could have removed container but failed to remove image for a number of reasons
        update.complete(success=False, message=e.message)
        raise e

def stopChute(update):
    """
    Stop a docker container based on the passed in update.

    :param update: The update object containing information about the chute.
    :type update: obj
    :returns: None
    """
    out.info('Attempting to stop chute %s\n' % (update.name))
    c = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
    c.stop(container=update.name)

def restartChute(update):
    """
    Start a docker container based on the passed in update.

    :param update: The update object containing information about the chute.
    :type update: obj
    :returns: None
    """
    out.info('Attempting to restart chute %s\n' % (update.name))
    c = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
    c.start(container=update.name)

    setup_net_interfaces(update)

def cleanUpDocker(validImages, validContainers):
    """
    Clean up any intermediate containers that may have resulted from a failure.

    :param validImages: A list of dicts containing the Id's of all the images that should exist on the system.
    :type validImages: list
    :param validContainers: A list of the Id's of all the containers that should exist on the system.
    :type validContainers: list
    :returns: None
    """
    c = docker.Client(base_url="unix://var/run/docker.sock", version='auto')

    #Clean up containers from failed build/start
    currContainers = c.containers(quiet=True, all=True)
    for cntr in currContainers:
        if not cntr in validContainers:
            out.info('Removing Invalid container with id: %s' % str(cntr.get('Id')))
            c.remove_container(container=cntr.get('Id'))

    #Clean up images from failed build
    currImages = c.images(quiet=True, all=False)
    for img in currImages:
        if not img in validImages:
            out.info('Removing Invalid image with id: %s' % str(img))
            c.remove_image(image=img)

def build_host_config(update, client=None):
    """
    Build the host_config dict for a docker container based on the passed in update.

    :param update: The update object containing information about the chute.
    :type update: obj
    :param client: Docker client object.
    :returns: (dict) The host_config dict which docker needs in order to create the container.
    """
    if client is None:
        client = docker.Client(base_url="unix://var/run/docker.sock", version='auto')

    if not hasattr(update.new, 'host_config') or update.new.host_config == None:
        config = dict()
    else:
        config = update.new.host_config

    host_conf = client.create_host_config(
        #TO support
        port_bindings=config.get('port_bindings'),
        dns=config.get('dns'),
        #not supported/managed by us
        #network_mode=update.host_config.get('network_mode'),
        network_mode='bridge',
        #extra_hosts=update.host_config.get('extra_hosts'),
        #binds=config.get('binds'),
        #links=config.get('links'),
        restart_policy={'MaximumRetryCount': 5, 'Name': 'on-failure'},
        devices=[],
        lxc_conf={},
        publish_all_ports=False,
        privileged=False,
        dns_search=[],
        volumes_from=None,
        cap_add=['NET_ADMIN'],
        cap_drop=[]
    )
    return host_conf


def setup_net_interfaces(update):
    """
    Link interfaces in the host to the internal interface in the docker container using pipework.

    :param update: The update object containing information about the chute.
    :type update: obj
    :returns: None
    """
    interfaces = update.new.getCache('networkInterfaces')
    for iface in interfaces:
        if iface.get('netType') == 'wifi':
            IP = iface.get('ipaddrWithPrefix')
            internalIntf = iface.get('internalIntf')
            externalIntf = iface.get('externalIntf')
        else: # pragma: no cover
            continue

        # Construct environment for pipework call.  It only seems to require
        # the PATH variable to include the directory containing the docker
        # client.  On Snappy this was not happening by default, which is why
        # this code is here.
        env = {"PATH": os.environ.get("PATH", "")}
        if settings.DOCKER_BIN_DIR not in env['PATH']:
            env['PATH'] += ":" + settings.DOCKER_BIN_DIR

        cmd = ['/apps/paradrop/current/bin/pipework', externalIntf, '-i',
               internalIntf, update.name,  IP]
        out.info("Calling: {}\n".format(" ".join(cmd)))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env)
            for line in proc.stdout:
                out.info("pipework: {}\n".format(line.strip()))
            for line in proc.stderr:
                out.warn("pipework: {}\n".format(line.strip()))
        except OSError as e:
            out.warn('Command "{}" failed\n'.format(" ".join(cmd)))
            out.exception(e, True)
            raise e


def prepare_environment(update):
    """
    Prepare environment variables for a chute container.
    """
    env = {
        'PARADROP_CHUTE_NAME': update.name,
        'PARADROP_ROUTER_ID': nexus.core.info.pdid
    }
    return env
