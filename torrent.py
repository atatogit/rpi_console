#!/usr/bin/python

from StringIO import StringIO
import gzip
import hashlib
import os
import re
import urllib2

def IsMagnetLink(uri_component):
    return uri_component.startswith("magnet:?")

def IsTorrentLink(uri_component):
    return uri_component.startswith("http://")
    
# Create a torrent file in the specified directory with the magnet link. If
# directory is empty, it writes the file in the current directory.
# Returns: the name of the file created. In case of error (if file exists, for
# instance), it raises an exception.
def CreateTorrentFileFromMagnet(magnet_link, directory):
    # Create a file with name: meta-<magnet_tail>.torrent inside directory, where
    #   <magnet_tail> is the part of the magnet link following "xt=urn:btih:".
    # Store "d10:magnet-uri<size>:<magnet>e" inside the file, where
    #   <size> is the size of <magnet>
    #   <magnet> is the magnet link  
    magnet_tail = re.search('xt=urn:btih:(.*)', magnet_link)
    torrent_hash = hashlib.md5(magnet_tail.group(1))
    fname = "meta-%s.torrent" % torrent_hash.hexdigest()
    if directory != "": fname = directory + "/" + fname
    data = "d10:magnet-uri%d:%se" % (len(magnet_link), magnet_link)
    __WriteFileNoOverwrite(fname, data)
    return fname
  
# Downloads the file from "link" and with it create a torrent file in the
# specified directory with the magnet link. If directory is empty, it writes the
# file in the current directory.
# Returns: the name of the file created. In case of error (if file exists, for
# instance), it raises an exception.
def DownloadTorrentFile(link, directory):
    request = urllib2.Request(link)
    request.add_header('Accept-encoding', 'gzip')
    data = urllib2.urlopen(link).read()
    response = urllib2.urlopen(request)
    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO(response.read())
        f = gzip.GzipFile(fileobj=buf)
        data = f.read()
    else:
        data = response.read()

    torrent_hash = hashlib.md5(data)
    fname = "download-%s.torrent" % torrent_hash.hexdigest()
    if directory != "": fname = directory + "/" + fname
    __WriteFileNoOverwrite(fname, data)
    return fname    

# Raises an exception on error.
def __WriteFileNoOverwrite(fname, data):
    fd = os.open(fname, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    f = os.fdopen(fd)
    f.write(data)
    f.close()
    

if __name__ == "__main__":
  CreateTorrentFileFromMagnet("xt=urn:btih:this-is-the-magnet-link", "mydir")
