/**
  Scripts for Dyphal, the Dynamic Photo Album.
  Copyright (c) Rennie deGraaf, 2005-2023.

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

/*jslint browser: true, passfail: false, plusplus: true, sub: true, vars: true, white: true, indent: 4, maxerr: 100, maxlen: 100 */

(function () {
"use strict";

var debug = false;
var logall = false;
var albumName = null; // name of the current album
var albumPath = null; // relative path to the album JSON file.  Begins with "." and ends with '/'.
var album = null; // object describing the current album
var page = null; // number of the current page, 0 for the album thumbnail view
var pages = []; // objects describing all pages that have been retrieved.  Based on album.photos.
var compact = false;

var compactThreshold = 750;


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


// Add a suffix-match method to String.
String.prototype.endsWith = function (suffix) {
    var lastIndex = this.lastIndexOf(suffix);
    return (-1 !== lastIndex) && (this.length === lastIndex + suffix.length);
};


// Check for compact layout and make layout changes if necessary.
function setScreenSize() {
    log("setScreenSize enter");

    try {
        // Check for a small screen and load the overrides if so.
        var small = false;
        if ((document.documentElement.clientWidth <= compactThreshold) || 
            (document.documentElement.clientHeight <= compactThreshold)) {
            small = true;
        }
        if (small &&
            (document.documentElement.clientHeight <= document.documentElement.clientWidth)) {
            // Compact view in landscape.  titlePanel is rotated and may be wider than the 
            // screen is tall; fix its size.
            document.getElementById("titlePanel").style.width = 
                                            (document.documentElement.clientHeight - 110) + "px";
        } else if (compact) {
            // Remove whatever overrides we may have applied.
            document.getElementById("titlePanel").style.width = "";
        }
        compact = small;
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("setScreenSize exit");
}


// Unload the debug stylesheet and update links
function unloadDebug() {
    log("unloadDebug enter");

    // Remove the debug class
    document.body.className = document.body.className.replace(/(?:^|\s)debug(?!\S)/g, "");

    // Remove the debug panel
    var debugPanel = document.getElementById("debugPanel");
    if (null !== debugPanel) {
        debugPanel.parentNode.removeChild(debugPanel);
    }

    // Remove the debug keyword from navivation links
    var links = document.querySelectorAll("a.navigationlink");
    var i;
    for (i = 0; i < links.length; ++i) {
        links[i].href = generatePhotoURL(links[i].getAttribute("data-target"));
    }

    log("unloadDebug exit");
}


// Load the debug stylesheet and update links
function loadDebug() {
    log("loadDebug enter");
    
    document.body.className += " debug";

    // Create a link to leave debug mode
    var debugPanel = document.createElement("div");
    debugPanel.id = "debugPanel";
    var debugLink = document.createElement("a");
    debugLink.id = "debugLink";
    debugLink.href = generatePhotoURL(page, true);
    debugLink.textContent = "Leave debug mode";
    debugPanel.appendChild(debugLink);
    document.getElementsByTagName("body")[0].appendChild(debugPanel);

    // Add the debug keyword to navigation links
    var links = document.querySelectorAll("a.navigationlink");
    var i;
    for (i = 0; i < links.length; ++i) {
        links[i].href = generatePhotoURL(links[i].getAttribute("data-target"));
    }

    log("loadDebug exit");
}


// Handle keystroke events
function keyHandler(evt) {
    try {
        var helpCheckbox = document.getElementById("helpCheckbox");
        var overlayCheckbox = document.getElementById("overlayCheckbox");
        if (helpCheckbox.checked && (27 /*escape*/ === evt.keyCode)) {
            helpCheckbox.checked = false;
            updateOverlays(); // Needed because of Android bug.
            evt.preventDefault();
        } else if (0 < page) {
            // On a photo page
            if (overlayCheckbox.checked && (27 /*escape*/ === evt.keyCode)) {
                overlayCheckbox.checked = false;
                updateOverlays(); // Needed because of Android bug.
                evt.preventDefault();
            } else if (13 /*enter*/ === evt.keyCode) {
                if (overlayCheckbox.checked) {
                    overlayCheckbox.checked = false;
                    updateOverlays(); // Needed because of Android bug.
                    evt.preventDefault();
                } else if (!helpCheckbox.checked) {
                    var photo = document.getElementById("photo");
                    if (undefined !== photo.click) {
                        photo.click();
                    } else {
                        // Android doesn't support obj.click()
                        var click = document.createEvent("HTMLEvents");
                        click.initEvent("click", true, true);
                        photo.dispatchEvent(click);
                    }
                    evt.preventDefault();
                }
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
            if (!helpCheckbox.checked && (13 /*enter*/ === evt.keyCode)) {
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
    // There are no differences between v1 and v2 photo JSON.  Early builds did not include a 
    // version field.
    if (undefined !== photoData.albumVersion 
        && 1 != photoData.albumVersion && 2 != photoData.albumVersion) {
        throw new Error("Album data version is not supported");
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
        document.getElementById("helpCheckbox").checked = false;
        document.getElementById("overlayCheckbox").checked = false;
        updateOverlays(); // Needed because of Android bug.

        if (0 < page) {
            var photoData = pages[page - 1];

            var photo = document.getElementById("photo");
            var photoOverlay = document.getElementById("photoOverlay");
            var photoAspect = photoData.width / photoData.height;
            var photoPanel = document.getElementById("contentPanel");
            var panelAspect = photoPanel.clientWidth / photoPanel.clientHeight;

            // Set the dimensions of the photo.
            if (photoAspect >= panelAspect) {
                // Constrained by width.
                var photoWidth = Math.min(photoPanel.clientWidth - (photo.offsetWidth - 
                                                            photo.clientWidth), photoData.width);
                photo.style["maxWidth"] = photoWidth + "px";
                photo.style["maxHeight"] = (photoWidth / photoAspect) + "px";
            } else {
                // Constrained by height.
                var photoHeight = Math.min(photoPanel.clientHeight - (photo.offsetHeight - 
                                                            photo.clientHeight), photoData.height);
                photo.style["maxHeight"] = photoHeight + "px";
                photo.style["maxWidth"] = photoHeight * photoAspect + "px";
            }

            // Set the dimensions of the overlay
            if ((photo.width !== parseInt(photoData.width, 10)) || 
                (photo.height !== parseInt(photoData.height, 10))) {
                var windowWidth = window.innerWidth;
                var windowHeight = window.innerHeight;
                var windowAspect = windowWidth / windowHeight;

                if (photoAspect >= windowAspect) {
                    // Constrained by width.
                    var overlayWidth = Math.min(windowWidth - 6, photoData.width);
                    photoOverlay.style["width"] = overlayWidth + "px";
                    photoOverlay.style["height"] = (overlayWidth / photoAspect) + "px";
                } else {
                    // Constrained by height.
                    var overlayHeight = Math.min(windowHeight - 6, photoData.height);
                    photoOverlay.style["height"] = overlayHeight + "px";
                    photoOverlay.style["width"] = (overlayHeight * photoAspect) + "px";
                }
                document.getElementById("overlay").style["display"] = "";
            } else {
                document.getElementById("overlay").style["display"] = "none";
            }

            photo.style["visibility"] = "visible";
            log("fitphoto: " + photo.style["height"] + " " + photo.style["width"]);
        }
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("fitPhoto exit");
}


// Display a photo and its metadata.
function loadPhotoContent() {
    log("loadPhotoContent enter");

    try {
        document.body.className = "photo" + (debug ? " debug" : "");
        document.getElementById("photo").style["visibility"] = "hidden";
        document.body.style["display"] = "";

        var photoData = pages[page - 1];

        // Load the photo.  Run "fitPhoto()" when it's ready.
        var photoElement = document.getElementById("photo");
        // Remove the event listeners before we change anything so that we don't get fitPhoto 
        // storms in IE8.
        photoElement.removeEventListener("load", fitPhoto, false);
        window.removeEventListener("resize", fitPhoto, false);
        window.removeEventListener("orientationchange", fitPhoto, false);
        // Webkit doesn't fire a load event if the src doesn't change.  So let's make sure it 
        // changes.
        photoElement.src = "";
        photoElement.style["width"] = photoData.width + "px";
        photoElement.style["height"] = photoData.height + "px";
        photoElement.addEventListener("load", fitPhoto, false);
        // Make sure that the event listener is in place before we set the photo
        photoElement.src = albumPath + photoData.photo;
        window.addEventListener("resize", fitPhoto, false);
        window.addEventListener("orientationchange", fitPhoto, false);

        document.getElementById("photoOverlay").style["backgroundImage"] = "url(" + albumPath 
                                                                    + photoData.photo + ")";
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
                captionElement.className = "captionItem";
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
        var rowElement, cellElement;
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

        document.getElementById("prevThumbPanel").style["visibility"] = "hidden";
        if (1 === page) {
            // No previous photo
            document.getElementById("prevImage").style["visibility"] = "hidden";
        } else {
            // Set the previous photo thumbnail
            var prevLinkElement = document.getElementById("prevThumbLink");
            prevLinkElement.href = generatePhotoURL(page - 1);
            prevLinkElement.setAttribute("data-target", page - 1);
            var prevThumbElement = document.getElementById("prevThumbImage");
            prevThumbElement.src = albumPath + album.photos[page - 1 - 1].thumbnail;
            if ("vertical" === album.photos[page - 1 - 1].orientation) {
                prevThumbElement.className = "vnavigation";
            } else {
                prevThumbElement.className = "hnavigation";
            }
            document.getElementById("prevThumbPanel").style["visibility"] = "";

            // Set the previous photo link
            prevLinkElement = document.getElementById("prevLink");
            prevLinkElement.href = generatePhotoURL(page - 1);
            prevLinkElement.setAttribute("data-target", page - 1);
            document.getElementById("prevImage").style["visibility"] = "";
        }

        document.getElementById("nextThumbPanel").style["visibility"] = "hidden";
        if (page === album.photos.length) {
            // No next photo
            document.getElementById("nextImage").style["visibility"] = "hidden";
        } else {
            // Set the next photo thumbnail
            var nextLinkElement = document.getElementById("nextThumbLink");
            nextLinkElement.href = generatePhotoURL(page + 1);
            nextLinkElement.setAttribute("data-target", page + 1);
            var nextThumbElement = document.getElementById("nextThumbImage");
            nextThumbElement.src = albumPath + album.photos[page - 1 + 1].thumbnail;
            if ("vertical" === album.photos[page - 1 + 1].orientation) {
                nextThumbElement.className = "vnavigation";
            } else {
                nextThumbElement.className = "hnavigation";
            }
            document.getElementById("nextThumbPanel").style["visibility"] = "";

            // Set the next photo link
            nextLinkElement = document.getElementById("nextLink");
            nextLinkElement.href = generatePhotoURL(page + 1);
            nextLinkElement.setAttribute("data-target", page + 1);
            document.getElementById("nextImage").style["visibility"] = "";
        }

        document.getElementById("indexLink").href = generatePhotoURL(0);
        if (debug) {
            document.getElementById("debugLink").href = generatePhotoURL(page, true);
        }

        cacheNext();
    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

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


// Display the album contents.
function loadAlbumContent() {
    log("loadAlbumContent enter");

    try {
        document.body.className = "album" + (debug ? " debug" : "");
        document.body.style["display"] = "";

        // Set the title
        document.title = album.title;
        document.getElementById("pageDescription").content = album.title + " photo album";
        document.getElementById("titleContent").textContent = album.title;
        document.getElementById("footerContent").textContent = album.footer;
        document.getElementById("description").textContent = album.description;

        var listElement = document.getElementById("thumbnailList");
        while (null !== listElement.firstChild) {
            listElement.removeChild(listElement.firstChild);
        }

        // Insert thumbnails as clones of a template
        var templateElement = document.createElement("li");
        templateElement.className = "thumbnail";
        var templateLinkElement = document.createElement("a");
        var templatePhotoElement = document.createElement("img");
        templatePhotoElement.alt = "Photo thumbnail";
        templateLinkElement.appendChild(templatePhotoElement);
        templateElement.appendChild(templateLinkElement);
        var i, itemElement, linkElement, photoElement;
        for (i = 0; i < album.photos.length; ++i) {
            itemElement = templateElement.cloneNode(true);
            linkElement = itemElement.getElementsByTagName("a")[0];
            photoElement = itemElement.getElementsByTagName("img")[0];
            linkElement.href = generatePhotoURL(i + 1);
            linkElement.className = "navigationlink";
            linkElement.setAttribute("data-target", i + 1);
            photoElement.src = albumPath + album.photos[i].thumbnail;
            if ("vertical" === album.photos[i].orientation) {
                photoElement.className = "vthumbnail";
            } else {
                photoElement.className = "hthumbnail";
            }
            listElement.appendChild(itemElement);
        }

        document.getElementById("indexLink").href = ".";
        if (debug) {
            document.getElementById("debugLink").href = generatePhotoURL(0, true);
        }

        cacheNext();

    } catch (e) {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadAlbumContent exit");
}


// Sanity-check the album description.  Error out if it's invalid.
function verifyAlbum(albumData) {
    if ((undefined === albumData) || 
        (undefined === albumData.albumVersion) || 
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
    // The only changes in v2 album JSON were the removal of fields that are not used by the 
    // web page.
    if (1 != albumData.albumVersion && 2 != albumData.albumVersion) {
        throw new Error("Album data version is not supported");
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
        document.addEventListener("keydown", keyHandler, false);
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


// Force the caption and property panels to have the same height in the compact layout.  Also 
// touch some layout-related property on everything that's style should change to work around an 
// Android bug.
function updateOverlays() {
    try {
        // Android versions prior to 4.4 seem to have a bug causing the caption, property, and 
        // footer panels not to be re-painted when their styles change due to the checkbox being 
        // changed.  Touching some layout-related property seems to force a re-paint.
        if (compact) {
            if (document.getElementById("overlayCheckbox").checked) {
                // In compact layout, force the caption and property panels to have the same 
                // height.
                var captionPanel = document.getElementById("captionPanel");
                var propertyPanel = document.getElementById("propertyPanel");
                var captionHeight = captionPanel.clientHeight;
                var propertyHeight = propertyPanel.clientHeight;
                var footerHeight = document.getElementById("footerPanel").clientHeight;
                var windowHeight = document.documentElement.clientHeight;
                if ((captionHeight + footerHeight > windowHeight) ||
                    (propertyHeight + footerHeight > windowHeight)) {
                    propertyPanel.style["height"] = (windowHeight - footerHeight) + "px";
                    captionPanel.style["height"] = (windowHeight - footerHeight) + "px";
                } else if (captionHeight > propertyHeight) {
                    propertyPanel.style["height"] = captionHeight + "px";
                    captionPanel.style["float"] = "none";
                } else {
                    captionPanel.style["height"] = propertyHeight + "px";
                    propertyPanel.style["float"] = "none";
                }
                document.getElementById("footerPanel").style["float"] = "none";
            } else {
                document.getElementById("captionPanel").style["height"] = "";
                document.getElementById("propertyPanel").style["height"] = "";
                document.getElementById("captionPanel").style["float"] = "";
                document.getElementById("propertyPanel").style["float"] = "";
                document.getElementById("footerPanel").style["float"] = "";
            }
        } else {
            if (document.getElementById("overlayCheckbox").checked) {
                document.getElementById("overlay").style["float"] = "none";
            } else {
                document.getElementById("overlay").style["float"] = "";
            }
        }
        if (document.getElementById("helpCheckbox").checked) {
            document.getElementById("helpTextPanel").style["float"] = "none";
        } else {
            document.getElementById("helpTextPanel").style["float"] = "";
        }
        
        // If the help text is longer than the screen and the user scrolls down 
        // before dismissing the help overlay, the browser should recognize 
        // that the current position is off the bottom of the document and 
        // return to the top.  Android doesn't do this reliably.
        window.scroll(0,0);
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Try to set full-screen mode on small screens.
// This can't be done in setScreenSize() because the FullScreen API only works
// in user-interaction event handlers, for security reasons.
function tryFullScreen(evt) {
    log ("tryFullScreen enter");

    try {
        // Scrolling is broken in full-screen MSIE 11, which completely breaks album view.  To work 
        // around this bug, don't request full screen on MSIE.  Using "Rob W"'s MSIE-detection 
        // code from https://stackoverflow.com/questions/9847580.
        if ((window.screen.width <= compactThreshold || window.screen.height < compactThreshold) 
            && !(/*@cc_on!@*/false || !!document.documentMode) /* is MSIE 6-11 */ ) {
            var rfs = document.documentElement.requestFullscreen 
                      || document.documentElement.webkitRequestFullScreen
                      || document.documentElement.mozRequestFullScreen
                      || document.documentElement.msRequestFullscreen;
            if (rfs) {
                rfs.call(document.documentElement);
            }
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
    log("tryFullScreen exit");
}


// Called when the document loads.  Display the requested page.
function start() {
    log("start enter");

    try {
        // DomContentLoaded doesn't get signalled when only the hash changes, but this does.
        // So let's make sure it's hidden.
        suppressWarning();

        document.getElementById("helpCheckbox").checked = false;
        document.getElementById("overlayCheckbox").checked = false;
        updateOverlays(); // Needed because of Android bug.
        document.getElementById("overlayCheckbox").addEventListener("change", updateOverlays);
        document.getElementById("helpCheckbox").addEventListener("change", updateOverlays);

        // Parse the page arguments
        var albumNameNew = null;
        var debugNew = false;
        var pageNew = 0;
        var args = window.location.hash.split("/");
        if ((1 === args.length) && ("" === args[0])) {
            // Kludge to support the current lack of an index view
            window.location = "albums.html";
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


/*
 * Swipe gestures for touch devices.
 * Touch tracking is broken on Android 3.x and 4.0, apparently fixed in 4.1, and regressed in 4.4.  
 * It's reportedly broken on some 4.2 and 4.3 builds as well.  The suggested "workaround" is to 
 * use event.disableDefault(), which breaks scrolling.  This variation on the workaround calls 
 * event.disableDefault() only if the first touchmove event appeared to be a side swipe; vertical 
 * scrolling should work as normal and horizontal scrolling can be achieved by first scrolling 
 * vertically.  This is based on Giovanni Di Gregorio's suggestion from 
 * https://stackoverflow.com/questions/20412982/javascript-any-workarounds-for-getting-chrome-for-
 * android-to-fire-off-touchmove/23145727#23145727
 */
var startPos = {x: null, y: null};
var startTime = null;
var swipeRatio = 4.0;
var swipeThreshold = 100;
var swipeTimeout = 333;

// Get the delta between the current touch position and the start position.
function getTouchDelta(evt) {
    var delta = {x: null, y: null};
    if (undefined !== evt.touches) {
        delta.x = parseInt(evt.changedTouches[0].clientX, 10) - startPos.x;
        delta.y = parseInt(evt.changedTouches[0].clientY, 10) - startPos.y;
    } else if (undefined !== evt.clientX) {
        // IE 10, 11
        delta.x = parseInt(evt.clientX, 10) - startPos.x;
        delta.y = parseInt(evt.clientY, 10) - startPos.y;
    }
    return delta;
}


// Android-specific workarounds for touch event bugs.
var swipeDetected;
function prevent(evt){
    evt.preventDefault();
}
function stopTracking(evt) {
    document.removeEventListener("touchmove", prevent, false);
}
function touchMove(evt) {
    try {
        var delta = getTouchDelta(evt);
        if(!swipeDetected) {
            if (Math.abs(delta.x / delta.y) >= swipeRatio) {
                swipeDetected = true;
            } else {
                stopTracking(evt);
            }
        }
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}
if (/Android/.test(navigator.userAgent)) {
    window.addEventListener("touchmove", touchMove, true);
    window.addEventListener("touchleave", stopTracking, true);
    window.addEventListener("touchcancel", stopTracking, true);
}


// Record the start of a touch.
function touchStart(evt) {
    try {
        if (/Android/.test(navigator.userAgent)) {
            swipeDetected = false;
            document.addEventListener("touchmove", prevent, false);
        }
        if (undefined !== evt.touches) {
            startPos.x = parseInt(evt.touches[0].clientX, 10);
            startPos.y = parseInt(evt.touches[0].clientY, 10);
        } else if (undefined !== evt.clientX) {
            // IE 10, 11
            startPos.x = parseInt(evt.clientX, 10);
            startPos.y = parseInt(evt.clientY, 10);
        }
        startTime = (new Date()).getTime();
    } catch (e) {
        error(e.name + ": " + e.message);
    }
}


// Determine if the touch that just ended was a left or right swipe, and if so, 
// change the photo being displayed.
function touchEnd(evt) {
    try {
        if (/Android/.test(navigator.userAgent)) {
            stopTracking(evt);
        }
        var deltaPos = getTouchDelta(evt);
        var deltaTime = (new Date()).getTime() - startTime;

        if ((swipeRatio < Math.abs(deltaPos.x/deltaPos.y)) && 
            (swipeThreshold < Math.abs(deltaPos.x)) && (swipeTimeout > deltaTime)) {
            if (0 > deltaPos.x) {
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
document.addEventListener("click", tryFullScreen, false);
document.addEventListener("keydown", tryFullScreen, false);
if (undefined !== window.ontouchstart) {
    window.addEventListener("touchstart", touchStart, true);
    window.addEventListener("touchend", touchEnd, true);
    window.addEventListener("touchend", tryFullScreen, true);
} else if (window.navigator.pointerEnabled) {
    // IE 11 touch events
    window.addEventListener("pointerdown", touchStart);
    window.addEventListener("pointerup", touchEnd);
    window.addEventListener("pointerup", tryFullScreen);
} else if (window.navigator.msPointerEnabled) {
    // IE 10 touch events
    window.addEventListener("MSPointerDown", touchStart);
    window.addEventListener("MSPointerUp", touchEnd);
    window.addEventListener("MSPointerUp", tryFullScreen);
}

log(navigator.appName);
log(navigator.userAgent);
log(window.innerWidth + "x" + window.innerHeight);

}());
