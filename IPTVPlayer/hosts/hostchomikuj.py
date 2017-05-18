﻿# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, ArticleContent, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, printDBG, printExc, formatBytes, CSearchHistoryHelper, GetLogoDir, GetCookieDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import urllib
from hashlib import md5
try:    import simplejson as json
except Exception: import json


###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
################################################### 
config.plugins.iptvplayer.Chomikuj_folder = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.Chomikuj_password = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.Chomikuj_login = ConfigText(default = "", fixed_size = False)

def GetConfigList():
    optionList = []

    optionList.append(getConfigListEntry("Folder startu", config.plugins.iptvplayer.Chomikuj_folder))
    optionList.append(getConfigListEntry("Nazwa chomika (login)", config.plugins.iptvplayer.Chomikuj_login))
    optionList.append(getConfigListEntry("Hasło do chomika", config.plugins.iptvplayer.Chomikuj_password))

    return optionList
###################################################


def gettytul():
    return 'Chomikuj'

class Chomikuj(CBaseHostClass):
    SERVICE = 'Chomikuj'
    MAINURL = 'http://mobile.chomikuj.pl/'
    LIST_FOLDER_URL  = 'api/v3/folders?parent=%s&page=%s'
    FILE_REQUEST_URL = 'api/v3/files/download?fileId='
    SEARCH_URL       = 'api/v3/files/search?Query=%s&PageNumber=%s&SizeMin=0&MediaType=%s'
    HTTP_JSON_HEADER  = {'User-Agent'  : "android/2.1.01 (a675e974-0def-4cbc-a955-ac6c6f99707b; unknown androVM for VirtualBox ('Tablet' version with phone caps))", 
                         'Content-Type': "application/json; charset=utf-8",
                         'Accept-Encoding':  'gzip'
                        }
    
    def __init__(self):
        printDBG("Chomikuj.__init__")
        CBaseHostClass.__init__(self, {'history':'Chomikuj'})
        self.loginData = {}
            
    def _getJItemStr(self, item, key, default=''):
        try:
            v = item.get(key, None)
        except Exception:
            v = None
        if None == v:
            return default
        return clean_html(u'%s' % v).encode('utf-8')
        
    def _getJItemNum(self, item, key, default=0):
        try:
            v = item.get(key, None)
        except Exception:
            v = None
        if None != v:
            try:
                NumberTypes = (int, long, float, complex)
            except NameError:
                NumberTypes = (int, long, float)
                
            if isinstance(v, NumberTypes):
                return v
        return default
            
    def requestJsonData(self, url, postData=None, addToken=True):
        addParams = {'header': dict(self.HTTP_JSON_HEADER)}
        if None != postData:
            addParams['raw_post_data'] = True
            data = postData
        else:
            data = ''
        if addToken:
            token    = "wzrwYua$.DSe8suk!`'2"
            token    = md5(url + data + token).hexdigest()
            addParams['header']['Token'] = token
        if 'ApiKey' in self.loginData: 
            addParams['header']['Api-Key'] = self.loginData['ApiKey']            
        
        sts, data = self.cm.getPage(Chomikuj.MAINURL + url, addParams, postData)
        #printDBG("=================================================")
        #printDBG(data)
        #printDBG("=================================================")
        if sts:
            try: data = json.loads(data)
            except Exception:
                printExc()
                sts = False
                data = {}
        else:
            data = {}
        return sts, data
    
    def listsMainMenu(self):
        printDBG("Chomikuj.listsMainMenu")
        data    = self.loginData['AccountBalance']
        quota   = formatBytes(1024 * (self._getJItemNum(data, 'QuotaAdditional', 0) + self._getJItemNum(data, 'QuotaLeft', 0)))
        account = self._getJItemStr(self.loginData, 'AccountName', '')
        title   = 'Chomik "%s" (%s transferu)' % (account, quota)
        self.addDir({'name':'category', 'title':title,                       'category':'account'})
        self.addDir({'name':'category', 'title':'Wyszukaj',                  'category':'search', 'search_item':True})
        self.addDir({'name':'category', 'title':'Historia wyszukiwania',     'category':'search_history'})
        
    def requestLoginData(self):
        url      = "api/v3/account/login"
        login    = config.plugins.iptvplayer.Chomikuj_login.value
        password = config.plugins.iptvplayer.Chomikuj_password.value
        loginData='{"AccountName":"%s","RefreshToken":"","Password":"%s"}' % (login, password)
        
        sts = False
        if '' == login or '' == password:
            self.sessionEx.open(MessageBox, 'Wprowadź dane do swojego konta Chomikuj.pl (Niebieski klawisz).', type = MessageBox.TYPE_INFO, timeout = 10 )
        else:
            sts, data = self.requestJsonData(url, loginData)
            if sts and 0 == self._getJItemNum(data, 'Code', -1):
                self.loginData = data
            else:
                sts = False
            if not sts:
                errorMessage = 'Problem z zalogowaniem użytkownika "%s".\n' % login
                if 404 == self._getJItemNum(data, 'Code', 0):
                    errorMessage += 'Konto nie istnieje.'
                elif 401 == self._getJItemNum(data, 'Code', 0):
                    errorMessage += 'Błędne hasło.'
                else:
                    errorMessage += 'Code="%d", message="%s".' % (self._getJItemNum(data, 'Code', 0), self._getJItemStr(data, 'Message', '')) 
                self.sessionEx.open(MessageBox, errorMessage, type = MessageBox.TYPE_INFO, timeout = 10 )
        return sts

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Chomikuj.listSearchResult cItem[%s], searchPattern[%s], searchType[%s]" % (cItem, searchPattern, searchType))
        page   = cItem.get('page', 1)
        
        map = {"images":"Image", "video":"Video", "music":"Music"}

        self.handleDataRequest(cItem, Chomikuj.SEARCH_URL % (urllib.quote_plus(searchPattern), page, map[searchType]))

    def handleProfile(self, cItem):
        printDBG("Chomikuj.handleProfile cItem[%s]" % cItem)
        parent = cItem.get('parent', 0)
        page   = cItem.get('page', 1)
        self.handleDataRequest(cItem, Chomikuj.LIST_FOLDER_URL % (parent, page))
        
    def handleDataRequest(self, cItem, url):
        sts, data = self.requestJsonData(url)
        if sts:
            printDBG(byteify(data))
            if 0 == self._getJItemNum(data, 'Code', -1):
                # list folders
                for item in data.get('Folders', []):
                    params = dict(cItem)
                    params.update({'title':self._getJItemStr(item, 'Name', ''), 'page': 1, 'parent':self._getJItemNum(item, 'Id', 0)})
                    self.addDir(params)
                    
                # list files
                if 'Files' in data:
                    key = 'Files'
                else:
                    key = 'Results'
                for item in data.get(key, []):
                    params = dict(cItem)
                    title = self._getJItemStr(item, 'FileName', '') 
                    size = formatBytes(1024 * self._getJItemNum(item, 'Size', 0))
                    desc = '%s, %s, %s' % (size, self._getJItemStr(item, 'MediaType', ''), self._getJItemStr(item, 'FileType', ''))
                    mediaType = self._getJItemStr(item, 'MediaType', '')
                    params.update({'title'  : title,
                                   'file_id': self._getJItemNum(item, 'FileId', -1),
                                   'icon'   : self._getJItemStr(item, 'SmallThumbnailImg', ''),
                                   'desc'   : desc,
                                   'size'   : size,
                                   'page'   : 1 })
                    if mediaType in ['Music', 'Video']:
                        params.update({'url':self._getJItemStr(item, 'StreamingUrl', '')})
                        self.addVideo(params)
                    elif 'Image' == mediaType:
                        params.update({'url':self._getJItemStr(item, 'ThumbnailImg', '')})
                        self.addPicture(params)
                    else:
                        printDBG('Chomikuj list file: unknown mediaType [%s]' % mediaType)
                
                if data.get('IsNextPageAvailable', False):
                    params = dict(cItem)
                    params.update({'title':'Następna strona', 'page': cItem.get('page', 1) + 1})
                    self.addDir(params)
                
    def getLinksForItem(self, cItem):
        printDBG("Chomikuj.getLinksForItem [%s]" % cItem['url'])
        videoUrls =[]
        # free 
        if cItem['url'].startswith('http'):
            videoUrls.append({'name':'Demo', 'url':cItem['url'], 'need_resolve':0})
        # full
        if -1 != cItem['file_id']:
            videoUrls.append({'name':'Full (%s)' % cItem['size'], 'url':'%s' % cItem['file_id'], 'need_resolve':1})
        return videoUrls
        
    def getVideoLinks(self, file_id):
        printDBG("Chomikuj.getLinkToFile [%s]" % file_id)
        urlTab = []
        try:
            sts, data = self.requestJsonData(Chomikuj.FILE_REQUEST_URL + file_id)
            if sts:
                url = self._getJItemStr(data, 'FileUrl', '')
                urlTab.append({'name':'direct', 'url':url})
        except Exception:
            printExc()
        return urlTab
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Chomikuj.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG( "Chomikuj.handleService: ---------> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        if None == name:
            if self.requestLoginData():
                self.listsMainMenu()
        elif 'account' == category:
            self.handleProfile(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

class IPTVHost(CHostBase):

    def getSearchTypes(self):
        searchTypesOptions = [] 
        searchTypesOptions.append(("Zdjęcia", "images"))
        searchTypesOptions.append(("Wideo", "video"))
        searchTypesOptions.append(("Audio", "music"))
        return searchTypesOptions

    def __init__(self):
        CHostBase.__init__(self, Chomikuj(), True)
