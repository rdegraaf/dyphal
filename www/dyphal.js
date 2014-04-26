/**
  Scripts for Dyphal, the Dynamic Photo Album.
  Copyright (c) Rennie deGraaf, 2005-2014.

  This program is free software; you can redistribute it and/or modify 
  it under the terms of the GNU General Public License as published by 
  the Free Software Foundation; either version 2 of the License, or (at 
  your option) version 3.

  This program is distributed in the hope that it will be useful, but 
  WITHOUT ANY WARRANTY; without even the implied warranty of 
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

/*jslint browser: true, passfail: false, plusplus: true, sub: true, vars: true, 
 white: true, indent: 4, maxerr: 100, maxlen: 100 */

(function () {
"use strict";

var debug = false;
var logall = false;
var albumName = null; // name of the current album
var albumPath = null; // relative path to the album JSON file.  Begins with "." and ends with '/'.
var album = null; // object describing the current album
var page = null; // number of the current page, 0 for the album thumbnail view
var pages = []; // objects describing all pages that have been retrieved.  Based on album.photos.
var overlayVisible = false;
var helpVisible = false;
var smallScreen = false;


// Display an error message in the warning panel
function error(msg) {
    var warningPanel = document.getElementById("warning");
    warningPanel.textContent = msg;
    warningPanel.style["display"] = "block";
}


// Log a message to the JavaScript console if running in debug mode.
function log(msg) {
    if (debug || logall) {
        try {
            console.log(msg);
        } catch (ignore) {}
    }
}


// Log a message to the JavaScript console
function warning(msg) {
    try {
        console.log(msg);
    } catch (ignore) {}
}


// Hide the warning panel
function suppressWarning() {
    document.getElementById("warning").style["display"] = "none";
}


// Return a URL to a photo.
function generatePhotoURL(index, suppressDebug) {
    var link = "#/" + encodeURIComponent(encodeURIComponent(albumName));
    if (null !== index && 0 !== index) {
        link += "/" + index;
    }
    if (debug && (true !== suppressDebug)) {
        link += "/debug";
    }
    return link;
}


// Retrieves and parses a JSON object, then makes a callback with the result 
// and any supplied arguments.  Catches any exceptions thrown by the callback, 
// which can be treated as fatal errors or as warnings.
function getJSON(object, callback, fatalErrors, args) {
    var req = new XMLHttpRequest();
    req.open("GET", object, true);
    req.onreadystatechange = function () {
        try {
            if (4 === req.readyState) {
                if (200 !== req.status) {
                    callback(req.status, null, args);
                } else {
                    var response;
                    if (req.response) {
                        // W3C
                        response = req.response;
                    } else {
                        // MSIE
                        response = req.responseText;
                    }
                    callback(req.status, JSON.parse(response), args);
                }
            }
        } catch (e) {
            if (fatalErrors) {
                error(e.name + ": " + e.message);
                throw e;
            } else {
                warning(e.name + ": " + e.message);
            }
        }
    };
    req.send();
}


// Poll 'test' with an exponential backoff starting with 'interval' milliseconds between attempts. 
// When it returns true, call 'action'.  If it fails 'maxtries' times, call 'error'.
function pollUntil(interval, maxtries, test, action, error) {
    if (test()) {
        action();
    } else if (maxtries > 0) {
        setTimeout(function () { pollUntil(interval * 2, maxtries - 1, test, action, error); }, 
                   interval);
    } else {
        error();
    }
}


// Add a suffix-match method to String.
String.prototype.endsWith = function (suffix) {
    var lastIndex = this.lastIndexOf(suffix);
    return (-1 !== lastIndex) && (this.length === lastIndex + suffix.length);
};


// Check for a small screen and make layout changes if necessary.
function setScreenSize() {
    log("setScreenSize enter");

    try {
        // Check for a small screen and load the overrides if so.
        var small = false;
        if (window.innerWidth < 600 || window.innerHeight < 600) {
            small = true;
        }
        if (small) {
            if (document.documentElement.clientHeight <= document.documentElement.clientWidth) {
                // landscape
                document.getElementById("titlePanel").style.width = 
                                            (document.documentElement.clientHeight - 110) + "px";
            }
        } else if (smallScreen) {
            // Remove whatever overrides we may have applied.
            document.getElementById("titlePanel").style.width = "";
        }
        smallScreen = small;
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("setScreenSize exit");
}


// Hide the full-screen photo overlay
function hidePhotoOverlay() {
    try {
        if (overlayVisible) {
            if (smallScreen) {
                var captionPanel = document.getElementById("captionPanel");
                var propertyPanel = document.getElementById("propertyPanel");

                // Remove event listeners.
                var photo = document.getElementById("photo");
                propertyPanel.removeEventListener("click", hidePhotoOverlay, false);
                captionPanel.removeEventListener("click", hidePhotoOverlay, false);
                photo.removeEventListener("click", hidePhotoOverlay, false);
                photo.addEventListener("click", showPhotoOverlay, false);

                // Remove the style overrides that we applied.
                document.getElementById("footerPanel").style["visibility"] = "";
                propertyPanel.style["visibility"] = "";
                captionPanel.style["visibility"] = "";
                propertyPanel.style["height"] = "";
                captionPanel.style["height"] = "";
            } else {
                document.getElementById("overlay").style["display"] = "none";
            }
            overlayVisible = false;
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Show the full-screen photo overlay
function showPhotoOverlay() {
    try {
        overlayVisible = true;
        if (smallScreen) {
            // On a small screen, show the photo caption and properties.
            var captionPanel = document.getElementById("captionPanel");
            var propertyPanel = document.getElementById("propertyPanel");

            // Make the caption and property panels have the same height.
            var captionHeight = captionPanel.clientHeight;
            var propertyHeight = propertyPanel.clientHeight;
            if (captionHeight > propertyHeight) {
                propertyPanel.style["height"] = captionHeight + "px";
            } else {
                captionPanel.style["height"] = propertyHeight + "px";
            }

            // Show the footer and photo metadata
            captionPanel.style["visibility"] = "visible";
            propertyPanel.style["visibility"] = "visible";
            document.getElementById("footerPanel").style["visibility"] = "visible";

            // Set event handlers to hide this stuff.
            var photo = document.getElementById("photo");
            photo.removeEventListener("click", showPhotoOverlay, false);
            photo.addEventListener("click", hidePhotoOverlay, false);
            captionPanel.addEventListener("click", hidePhotoOverlay, false);
            propertyPanel.addEventListener("click", hidePhotoOverlay, false);
        } else {
            // On a normal screen, show the photo at its full size if it isn't already.
            var photoData = pages[page - 1];
            var photo = document.getElementById("photo");
            if ((photo.width != photoData.width) || (photo.height != photoData.height)) {
                var overlay = document.getElementById("overlay");
                overlay.style["display"] = "block";
                overlay.addEventListener("click", hidePhotoOverlay, false);
            }
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Hide the full-screen help overlay
function hideHelp() {
    try {
        if (helpVisible) {
            document.getElementById("helpTextPanel").style["display"] = "none";
            helpVisible = false;
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Show the full-screen help overlay
function showHelp() {
    try {
        var help = document.getElementById("helpTextPanel");
        help.style["display"] = "block";
        help.addEventListener("click", hideHelp, false);

        // Displaying the help text may resize the window.  Delay setting helpVisible to ensure 
        // that the call to fitPhoto() on the initial resize doesn't immediately suppress help.
        setTimeout(function () { helpVisible = true; }, 50);
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Unload the debug stylesheet and update links
function unloadDebug() {
    log("unloadDebug enter");

    // Unload the debug stylesheet
    var cssElement = document.getElementById("debugStylesheet");
    cssElement.parentNode.removeChild(cssElement);

    // Remove the debug panel
    var debugPanel = document.getElementById("debugPanel");
    debugPanel.parentNode.removeChild(debugPanel);

    // Remove the debug keyword from navivation links
    var links = document.querySelectorAll("a.navigationlink");
    var i;
    for (i = 0; i < links.length; ++i) {
        links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));
    }

    // resume the load process, now that we've removed the debug document elements.
    start();

    log("unloadDebug exit");
}


// Leave debug mode due to failure of the debug stylesheet to load
function loadDebugError() {
    log("loadDebugError enter");

    try {
        debug = false;

        // Unload the debug stylesheet
        var cssElement = document.getElementById("debugStylesheet");
        cssElement.parentNode.removeChild(cssElement);

        // Remove the debug tag from the URL
        window.location.hash = generatePhotoURL(page, false);
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadDebugError exit");
}


// Update the page after the debug stylesheet has loaded
function loadDebugAfterStylesheet() {
    log("loadDebugAfterStylesheet enter");

    try {
        // Create a link to leave debug mode
        var debugPanel = document.createElement("div");
        debugPanel.setAttribute("id", "debugPanel");
        var debugLink = document.createElement("a");
        debugLink.setAttribute("id", "debugLink");
        debugLink.setAttribute("href", generatePhotoURL(page, true));
        debugLink.textContent = "Leave debug mode";
        debugPanel.appendChild(debugLink);
        document.getElementsByTagName("body")[0].appendChild(debugPanel);

        // Add the debug keyword to navigation links
        var links = document.querySelectorAll("a.navigationlink");
        var i;
        for (i = 0; i < links.length; ++i) {
            links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));
        }

        // resume the load process, now that we have the debug document elements.
        start();
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadDebugAfterStylesheet exit");
}


// Check if the browser is known to not fire load events on link elements.
function brokenLoadEventOnLink() {
    // Load events on link elements are broken on Android versions prior to 4.4
    var regex = /Android ([0-9]+)\.([0-9]+)(?:[^0-9]|$)/i;
    var match = regex.exec(navigator.userAgent);
    if (null !== match && 3 === match.length) {
        return (match[1] < 4 || match[2] < 4);
    }

    return false;
}


// Load the debug stylesheet and update links
function loadDebug() {
    log("loadDebug enter");

    // Load the debug stylesheet
    var cssElement = document.createElement("link");
    // We'll only update the links if the stylesheet loads correctly.
    cssElement.addEventListener("load", loadDebugAfterStylesheet, false);
    cssElement.addEventListener("error", loadDebugError, false);
    cssElement.setAttribute("rel", "stylesheet");
    cssElement.setAttribute("href", "debug.css");
    cssElement.setAttribute("id", "debugStylesheet");
    document.getElementsByTagName("head")[0].appendChild(cssElement);

    // Some browsers don't call load events on link objects.  So we need to poll 
    // until the stylesheet is present.
    if (brokenLoadEventOnLink()) {
        pollUntil(50, 6, function () { return document.styleSheets[document.styleSheets.length - 1]
                                                                .href.endsWith("/debug.css"); }, 
                  loadDebugAfterStylesheet, loadDebugError);
    }

    log("loadDebug exit");
}


// Handle keystroke events
function keyHandler(evt) {
    try {
        if (helpVisible && (27 /*escape*/ === evt.keyCode)) {
            hideHelp();
            evt.preventDefault();
        } else if (0 < page) {
            // On a photo page
            if (overlayVisible && (27 /*escape*/ === evt.keyCode)) {
                hidePhotoOverlay();
                evt.preventDefault();
            } else if (13 /*enter*/ === evt.keyCode) {
                if (overlayVisible) {
                    hidePhotoOverlay();
                } else if (!helpVisible) {
                    document.getElementById("photo").click();
                }
                evt.preventDefault();
            } else if ((34 /*page down*/ === evt.keyCode) || (32 /*space*/ === evt.keyCode)) {
                if (album.photos.length !== page) {
                    document.location.href = generatePhotoURL(page + 1);
                }
                evt.preventDefault();
            } else if ((33 /*page up*/ === evt.keyCode) || (8 /*backspace*/ === evt.keyCode)) {
                if (1 !== page) {
                    document.location.href = generatePhotoURL(page - 1);
                }
                evt.preventDefault();
            } else if ((36 /*home*/ === evt.keyCode) || (27 /*escape*/ === evt.keyCode)) {
                document.location.href = generatePhotoURL(0);
                evt.preventDefault();
            }
        } else if (0 === page) {
            // On an album page
            if (!helpVisible && (13 /*enter*/ === evt.keyCode)) {
                document.location.href = generatePhotoURL(1);
                evt.preventDefault();
            }
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Verify that a photo description is well-formed.
function verifyPhoto(photoData) {
    if ((undefined === photoData) || 
        (undefined === photoData.photo) || 
        (undefined === photoData.width) || 
        (undefined === photoData.height) || 
        (undefined === photoData.properties) || 
        (undefined === photoData.caption)) {
        throw new Error("Photo data is invalid");
    }
}


// Cache a photo
function cachePhoto(status, photoData, args) {
    log("cachePhoto enter");

    if (200 !== status) {
        throw new Error("Photo data is missing");
    } else {
        if (undefined === pages[args.page]) {
            verifyPhoto(photoData);
            pages[args.page] = photoData;
            var preload = new Image();
            preload.src = albumPath + photoData.photo;
        }
    }

    log("cachePhoto exit");
}


// Fetch and cache the JSON for the next page
function cacheNext() {
    log("cacheNext enter");

    if (null !== page && page < album.photos.length && undefined === pages[page]) {
        getJSON(albumPath + album.metadataDir + album.photos[page].name + ".json", cachePhoto, 
                false, {"page" : page});
    }

    log("cacheNext exit");
}


// Scale a photo to fit in its frame
function fitPhoto() {
    log("fitPhoto enter");

    try {
        hidePhotoOverlay();
        hideHelp();

        if (0 < page) {
            var photoData = pages[page - 1];

            var photo = document.getElementById("photo");
            var photoOverlay = document.getElementById("photoOverlay");
            var photoAspect = photoData.width / photoData.height;
            var photoPanel = document.getElementById("contentPanel");
            var panelAspect = photoPanel.clientWidth / photoPanel.clientHeight;

            var windowWidth = document.documentElement.clientWidth - 10;
            var windowHeight = document.documentElement.clientHeight - 10;
            var windowAspect = windowWidth / windowHeight;

            // Set the dimensions of the photo.
            if (photoAspect >= panelAspect) {
                // Constrained by width.
                var photoWidth = Math.min(photoPanel.clientWidth, photoData.width);
                photo.style["width"] = photoWidth + "px";
                photo.style["height"] = (photoWidth / photoAspect) + "px";
            } else {
                // Constrained by height.
                var photoHeight = Math.min(photoPanel.clientHeight, photoData.height);
                photo.style["height"] = photoHeight + "px";
                photo.style["width"] = (photoHeight * photoAspect) + "px";
            }

            // Set the dimensions of the overlay
            if (photoAspect >= windowAspect) {
                // Constrained by width.
                var overlayWidth = Math.min(windowWidth, photoData.width);
                photoOverlay.style["width"] =  overlayWidth + "px";
                photoOverlay.style["height"] = (overlayWidth / photoAspect) + "px";
            } else {
                // Constrained by height.
                var overlayHeight = Math.min(windowHeight, photoData.height);
                photoOverlay.style["height"] = overlayHeight + "px";
                photoOverlay.style["width"] = (overlayHeight * photoAspect) + "px";
            }
            photo.addEventListener("click", showPhotoOverlay, false);

            photo.style["visibility"] = "visible";
            log("fitphoto: " + photo.style["height"] + " " + photo.style["width"]);
        }
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("fitPhoto exit");
}


// Display a photo
function loadPhotoAfterStylesheet() {
    log("loadPhotoAfterStylesheet enter");

    try {
        if (0 < page) {
            // Load the photo.  Run "fitPhoto()" when it's ready.
            var photoData = pages[page - 1];
            var photoElement = document.getElementById("photo");
            // Remove the event listeners before we change anything so that we don't get fitPhoto 
            // storms in IE8
            photoElement.removeEventListener("load", fitPhoto, false);
            window.removeEventListener("resize", fitPhoto, false);
            window.removeEventListener("orientationchange", fitPhoto, false);
            // Webkit doesn't fire a load event if the src doesn't change.  So let's make sure it 
            // changes.
            photoElement.setAttribute("src", "");
            photoElement.style["width"] = photoData.width + "px";
            photoElement.style["height"] = photoData.height + "px";
            photoElement.addEventListener("load", fitPhoto, false);
            // Make sure that the event listener is in place before we set the photo
            photoElement.setAttribute("src", albumPath + photoData.photo);
            window.addEventListener("resize", fitPhoto, false);
            window.addEventListener("orientationchange", fitPhoto, false);

            document.getElementById("photoOverlay").style["backgroundImage"] = "url(" + albumPath 
                                                                        + photoData.photo + ")";
        }
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadPhotoAfterStylesheet exit");
}


// Display a photo and its description
function loadPhotoContent() {
    log("loadPhotoContent enter");

    var photoData = pages[page - 1];

    document.getElementById("photo").style["visibility"] = "hidden";

    // If we're not already using the photo stylesheet, the photo won't re-size 
    // properly unless we load the stylesheet first.  Chrome doesn't fire a 
    // load event when the target of a link element changes, so we need to 
    // create a new link element.
    var cssElement = document.getElementById("stylesheet");
    if ("photo.css" !== cssElement.getAttribute("href")) {
        var cssElementNew = cssElement.cloneNode();
        cssElementNew.addEventListener("load", loadPhotoAfterStylesheet, false);
        cssElementNew.setAttribute("href", "photo.css");
        cssElement.parentNode.replaceChild(cssElementNew, cssElement);

        // Some browsers don't call load events on link objects.  So we need to 
        // poll until the stylesheet is present.
        if (brokenLoadEventOnLink()) {
            pollUntil(50, 6, function () { return (document.styleSheets.length >= 2)
                                        && document.styleSheets[1].href.endsWith("/photo.css"); },
                      loadPhotoAfterStylesheet, function () { error("Error loading stylesheet"); });
        }
    } else {
        loadPhotoAfterStylesheet();
    }

    // Set the title
    document.title = album.title + " (" + page + "/" + album.photos.length + ")";
    document.getElementById("titleContent").textContent = album.title;
    document.getElementById("footerContent").textContent = album.footer;

    // Set the photo index
    document.getElementById("index").textContent = page + "/" + album.photos.length;

    // Load photo caption
    var captionPanel = document.getElementById("captionPanel");
    while (null !== captionPanel.firstChild) {
        captionPanel.removeChild(captionPanel.firstChild);
    }
    var idx, captionElement;
    for (idx in photoData.caption) {
        if (photoData.caption.hasOwnProperty(idx)) {
            captionElement = document.createElement("p");
            captionElement.setAttribute("class", "captionItem");
            captionElement.textContent = photoData.caption[idx];
            captionPanel.appendChild(captionElement);
        }
    }

    // Load photo properties
    var propertyTable = document.getElementById("propertyTable");
    var rows = propertyTable.getElementsByTagName("tr");
    while (0 !== rows.length) {
        propertyTable.removeChild(rows[0]);
    }
    var idx, rowElement, cellElement;
    for (idx in photoData.properties) {
        if (photoData.properties.hasOwnProperty(idx)) {
            rowElement = document.createElement("tr");
            cellElement = document.createElement("td");
            cellElement.textContent = photoData.properties[idx][0];
            rowElement.appendChild(cellElement);

            cellElement = document.createElement("td");
            cellElement.textContent = photoData.properties[idx][1];
            rowElement.appendChild(cellElement);

            propertyTable.appendChild(rowElement);
        }
    }

    if (1 === page) {
        // No previous photo
        document.getElementById("prevThumbPanel").style["visibility"] = "hidden";
        document.getElementById("prevImage").style["visibility"] = "hidden";
    } else {
        // Set the previous photo thumbnail
        var prevLinkElement = document.getElementById("prevThumbLink");
        prevLinkElement.setAttribute("href", generatePhotoURL(page - 1));
        prevLinkElement.setAttribute("data-target", page - 1);
        var prevThumbElement = document.getElementById("prevThumbImage");
        prevThumbElement.setAttribute("src", albumPath + album.photos[page - 1 - 1].thumbnail);
        if ("vertical" === album.photos[page - 1 - 1].orientation) {
            prevThumbElement.setAttribute("class", "vnavigation");
        } else {
            prevThumbElement.setAttribute("class", "hnavigation");
        }
        document.getElementById("prevThumbPanel").style["visibility"] = "visible";

        // Set the previous photo link
        prevLinkElement = document.getElementById("prevLink");
        prevLinkElement.setAttribute("href", generatePhotoURL(page - 1));
        prevLinkElement.setAttribute("data-target", page - 1);
        document.getElementById("prevImage").style["visibility"] = "visible";
    }

    if (page === album.photos.length) {
        // No next photo
        document.getElementById("nextThumbPanel").style["visibility"] = "hidden";
        document.getElementById("nextImage").style["visibility"] = "hidden";
    } else {
        // Set the next photo thumbnail
        var nextLinkElement = document.getElementById("nextThumbLink");
        nextLinkElement.setAttribute("href", generatePhotoURL(page + 1));
        nextLinkElement.setAttribute("data-target", page + 1);
        var nextThumbElement = document.getElementById("nextThumbImage");
        nextThumbElement.setAttribute("src", albumPath + album.photos[page - 1 + 1].thumbnail);
        if ("vertical" === album.photos[page - 1 + 1].orientation) {
            nextThumbElement.setAttribute("class", "vnavigation");
        } else {
            nextThumbElement.setAttribute("class", "hnavigation");
        }
        document.getElementById("nextThumbPanel").style["visibility"] = "visible";

        // Set the next photo link
        nextLinkElement = document.getElementById("nextLink");
        nextLinkElement.setAttribute("href", generatePhotoURL(page + 1));
        nextLinkElement.setAttribute("data-target", page + 1);
        document.getElementById("nextImage").style["visibility"] = "visible";
    }

    document.getElementById("indexLink").setAttribute("href", generatePhotoURL(0));
    if (debug) {
        document.getElementById("debugLink").setAttribute("href", generatePhotoURL(page, true));
    }

    cacheNext();

    log("loadPhotoContent exit");
}


// Load a photo description, then display the photo.
function loadPhoto(status, photoData, args) {
    log("loadPhoto enter");

    if (200 !== status) {
        throw new Error("Photo data is missing");
    } else {
        if (page === args.page) {
            verifyPhoto(photoData);
            pages[page - 1] = photoData;
            loadPhotoContent();
        }
    }

    log("loadPhoto exit");
}


// Display the album contents
function loadAlbumContent() {
    log("loadAlbumContent enter");

    document.getElementById("stylesheet").setAttribute("href", "album.css");

    // Set the title
    document.title = album.title;
    document.getElementById("titleContent").textContent = album.title;
    document.getElementById("footerContent").textContent = album.footer;
    document.getElementById("description").textContent = album.description;

    var listElement = document.getElementById("thumbnailList");
    while (null !== listElement.firstChild) {
        listElement.removeChild(listElement.firstChild);
    }

    // Insert thumbnails as clones of a template
    var templateElement = document.createElement("li");
    templateElement.setAttribute("class", "thumbnail");
    var templateLinkElement = document.createElement("a");
    var templatePhotoElement = document.createElement("img");
    templatePhotoElement.setAttribute("alt", "Photo thumbnail");
    templateLinkElement.appendChild(templatePhotoElement);
    templateElement.appendChild(templateLinkElement);
    var i, itemElement, linkElement, photoElement;
    for (i = 0; i < album.photos.length; ++i) {
        itemElement = templateElement.cloneNode(true);
        linkElement = itemElement.getElementsByTagName("a")[0];
        photoElement = itemElement.getElementsByTagName("img")[0];
        linkElement.setAttribute("href", generatePhotoURL(i + 1));
        linkElement.setAttribute("class", "navigationlink");
        linkElement.setAttribute("data-target", i + 1);
        photoElement.setAttribute("src", albumPath + album.photos[i].thumbnail);
        if ("vertical" === album.photos[i].orientation) {
            photoElement.setAttribute("class", "vthumbnail");
        } else {
            photoElement.setAttribute("class", "hthumbnail");
        }
        listElement.appendChild(itemElement);
    }

    document.getElementById("indexLink").setAttribute("href", ".");
    if (debug) {
        document.getElementById("debugLink").setAttribute("href", generatePhotoURL(0, true));
    }

    cacheNext();

    log("loadAlbumContent exit");
}


// Sanity-check the album description.  Error out if it's invalid.
function verifyAlbum(albumData) {
    if ((undefined === albumData) || 
        (undefined === albumData.title) || 
        (undefined === albumData.footer) || 
        (undefined === albumData.description) || 
        (undefined === albumData.metadataDir) || 
        (undefined === albumData.photos)) {
        throw new Error("Album data is invalid");
    }
    var i;
    for (i = 0; i < albumData.photos.length; ++i) {
        if ((undefined === albumData.photos[i]) || 
            (undefined === albumData.photos[i].name) || 
            (undefined === albumData.photos[i].thumbnail) || 
            (undefined === albumData.photos[i].orientation)) {
            throw new Error("Album data is invalid");
        }
    }
}


// Load the album description, then use it to display the requested page
function loadAlbum(status, albumData, args) {
    log("loadAlbum enter");

    if (200 !== status) {
        throw new Error("Album data is missing");
    } else {
        verifyAlbum(albumData);
        album = albumData;
        // Now that we have the album loaded, set the keystroke handler
        document.addEventListener("keypress", keyHandler, false);
        if (0 === page) {
            loadAlbumContent();
        } else if (page > album.photos.length) {
            throw new Error("Photo number out of range");
        } else if (undefined === pages[page - 1]) {
            getJSON(albumPath + album.metadataDir + album.photos[page - 1].name + ".json", 
                    loadPhoto, true, {"page" : page});
        } else {
            loadPhotoContent();
        }
    }

    log("loadAlbum exit");
}


// Called when the document loads.  Display the requested page.
function start() {
    log("start enter");

    try {
        // DomContentLoaded doesn't get signalled when only the hash changes, but this does.
        // So let's make sure it's hidden.
        suppressWarning();

        hidePhotoOverlay();
        hideHelp();

        document.getElementById("helpLink").addEventListener("click", showHelp, false);

        // Parse the page arguments
        var albumNameNew = null;
        var debugNew = false;
        var pageNew = 0;
        var args = window.location.hash.split("/");
        if ((1 === args.length) && ("" === args[0])) {
            // Kludge to support the current lack of an index view
            window.location = "album-list.html";
            return;
        }
        if ((2 > args.length) || ("" === args[1]) || ("#" !== args[0])) {
            throw new Error("Incorrect page arguments");
        }
        albumNameNew = decodeURIComponent(args[1]);
        if ((3 === args.length) && ("debug" === args[2])) {
            debugNew = true;
        } else if (3 <= args.length) {
            if (/^[0-9]+$/.test(args[2])) {
                pageNew = parseInt(args[2], 10);
                if ((4 === args.length) && ("debug" === args[3])) {
                    debugNew = true;
                } else if (4 <= args.length) {
                    throw new Error("Incorrect page arguments");
                }
            } else {
                throw new Error("Incorrect page arguments");
            }
        }

        // We need to set albumName before we set debug so that loadDebugError() can work.
        if (albumName !== albumNameNew) {
            albumName = albumNameNew;
            albumPath = "./" + albumName.replace(/[^\/]+$/, '');
            album = null;
            page = null;
        }

        if (debug !== debugNew) {
            debug = debugNew;
            if (debugNew) {
                loadDebug();
            } else {
                unloadDebug();
            }

            // These methods register load callbacks that change the DOM, so we need to wait until 
            // they complete before we can finish loading
            return;
        }

        if (page !== pageNew) {
            page = pageNew;
            if (null === album) {
                getJSON("./" + albumName + ".json", loadAlbum, true, null);
            } else if (0 === page) {
                loadAlbumContent();
            } else if (page > album.photos.length) {
                error("Photo number out of range");
            } else if (undefined === pages[page - 1]) {
                getJSON(albumPath + album.metadataDir + album.photos[page - 1].name + ".json", 
                        loadPhoto, true, {"page" : page});
            } else {
                loadPhotoContent();
            }
        }
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("start exit");
}


// Record the start of a touch
var currentX = null;
var currentY = null;
function touchStart(evt) {
    try {
        currentX = parseInt(evt.touches[0].clientX, 10);
        currentY = parseInt(evt.touches[0].clientY, 10);
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Determine if the touch that just ended was a left or right swipe, and if so, 
// change the photo being displayed.
function touchEnd(evt) {
    try {
        var thresholdY = 40;
        var thresholdX = 100;

        var motionX = parseInt(evt.changedTouches[0].clientX, 10) - currentX;
        var motionY = parseInt(evt.changedTouches[0].clientY, 10) - currentY;

        if ((thresholdY > Math.abs(motionY)) && (thresholdX < Math.abs(motionX))) {
            if (0 > motionX) {
                if (0 < page && album.photos.length !== page) {
                    document.location.href = generatePhotoURL(page + 1);
                }
            } else {
                if (1 <= page) {
                    document.location.href = generatePhotoURL(page - 1);
                }
            }
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Set up event listeners
window.addEventListener("load", start, false);
window.addEventListener("hashchange", start, false);
// Since JavaScript is clearly enabled, hide the warning as early as possible
document.addEventListener("DOMContentLoaded", suppressWarning, false);
document.addEventListener("DOMContentLoaded", setScreenSize, false);
window.addEventListener("resize", setScreenSize, false);
window.addEventListener("orientationchange", setScreenSize, false);
window.addEventListener("touchstart", touchStart);
window.addEventListener("touchend", touchEnd);

log(navigator.appName);
log(navigator.userAgent);
log(window.innerWidth + "x" + window.innerHeight);

})();
