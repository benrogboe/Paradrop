import json

from pdtools.lib import nexus
from pdtools.lib.output import out
from pdtools.lib.pdutils import json2str, str2json, timeint, urlDecodeMe

from paradrop.lib.api.pdrest import APIDecorator
from paradrop.lib.api import pdapi

from paradrop.lib.config import hostconfig

class ConfigAPI(object):
    """
    Configuration API.

    This class handles HTTP API calls related to router configuration.
    """
    def __init__(self, rest):
        self.rest = rest
        self.rest.register('GET', '^/v1/hostconfig', self.GET_hostconfig)
        self.rest.register('PUT', '^/v1/hostconfig', self.PUT_hostconfig)
        self.rest.register('PUT', '^/v1/pdid', self.PUT_pdid)
        self.rest.register('PUT', '^/v1/apitoken', self.PUT_apitoken)

    @APIDecorator()
    def GET_hostconfig(self, apiPkg):
        """
        Query for router host configuration.

        Returns:
            an object containing host configuration.
        """
        config = hostconfig.prepareHostConfig()
        result = json.dumps(config, separators=(',',':'))
        apiPkg.request.setHeader('Content-Type', 'application/json')
        apiPkg.setSuccess(result)

    @APIDecorator(requiredArgs=["config"])
    def PUT_hostconfig(self, apiPkg):
        """
        Set the router host configuration.

        Arguments:
            config: object following same format as the GET result.
        Returns:
            an object containing message and success fields.
        """
        config = apiPkg.inputArgs.get('config')
        hostconfig.save(config)

        update = dict(updateClass='ROUTER', updateType='sethostconfig',
                name='__HOSTCONFIG__', tok=timeint(), pkg=apiPkg,
                func=self.rest.complete)
        self.rest.configurer.updateList(**update)

        apiPkg.request.setHeader('Content-Type', 'application/json')

        # Tell our system we aren't done yet (the configurer will deal with
        # closing the connection)
        apiPkg.setNotDoneYet()

    @APIDecorator(requiredArgs=["pdid"])
    def PUT_pdid(self, apiPkg):
        """
        Set the router identity (pdid).

        Arguments:
            pdid: a string (e.g. pd.lance.halo06)
        """
        pdid = apiPkg.inputArgs.get('pdid')
        nexus.core.provision(pdid, None)
        apiPkg.setSuccess("")

    @APIDecorator(requiredArgs=["apitoken"])
    def PUT_apitoken(self, apiPkg):
        """
        Set the router API token.

        Arguments:
            apitoken: a string
        """
        apitoken = apiPkg.inputArgs.get('apitoken')
        nexus.core.saveKey(apitoken, 'apitoken')
        apiPkg.setSuccess("")
