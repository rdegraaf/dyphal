/**
  Scripts for Dyphal, the Dynamic Photo Album.
  Copyright (c) Rennie deGraaf, 2005-2014.  All rights reserved.
*/

var debug=false;
var albumName=null; // name of the current album
var albumPath=null; // relative path to the album JSON file.  Begins with "." and ends with '/'.
var album=null; // object describing the current album
var page=null; // number of the current page, 0 for the album thumbnail view
var pages=[]; // objects describing all pages that have been retrieved.  Corresponds to album.photos.
var overlayVisible=false;
var helpVisible = false;
var logall = false;


// Set up event listeners
window.addEventListener("load", start, false);
window.addEventListener("hashchange", start, false);
// Since JavaScript is clearly enabled, hide the warning as early as possible
document.addEventListener("DOMContentLoaded", suppressWarning, false);
window.addEventListener("touchstart", touchStart);
window.addEventListener("touchend", touchEnd);

log(navigator.appName);
log(navigator.userAgent);

// Display an error message in the warning panel
function error(msg)
{
    var warningPanel = document.getElementById("warning");
    warningPanel.textContent = msg;
    warningPanel.style["display"] = "block";
}

function log(msg)
{
    if (debug || logall)
    {
        try
        {
            console.log(msg);
        }
        catch (e)
        {}
    }
}


// Log a message to the JavaScript console
function warning(msg)
{
    try
    {
        console.log(msg);
    }
    catch (e)
    {}
}


// Hide the warning panel
function suppressWarning()
{
    document.getElementById("warning").style["display"] = "none";
}


// Called when the document loads.  Display the requested page.
function start()
{
    log("start enter");

    try
    {
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
        if ((1 == args.length) && ("" == args[0]))
        {
            // Kludge to support the current lack of an index view
            window.location = "album-list.html";
            return;
        }
        if ((2 > args.length) || ("" == args[1]) || ("#" != args[0]))
            throw new Error("Incorrect page arguments");
        albumNameNew = decodeURIComponent(args[1]);
        if ((3 == args.length) && ("debug" == args[2]))
            debugNew = true;
        else if (3 <= args.length)
        {
            if (/^[0-9]+$/.test(args[2]))
            {
                pageNew = parseInt(args[2])
                if ((4 == args.length) && ("debug" == args[3]))
                    debugNew = true;
                else if (4 <= args.length)
                    throw new Error("Incorrect page arguments");
            }
            else
                throw new Error("Incorrect page arguments");
        }

        // We need to set albumName before we set debug so that loadDebugError() can work.
        if (albumName != albumNameNew)
        {
            albumName = albumNameNew;
            albumPath = "./" + albumName.replace(/[^\/]+$/, '');
            album = null;
            page = null;
        }

        if (debug != debugNew)
        {
            debug = debugNew;
            if (debugNew)
                loadDebug();
            else
                unloadDebug();

            // These methods register load callbacks that change the DOM, so we need to wait until 
            // they complete before we can finish loading
            return;
        }

        if (page != pageNew)
        {
            page = pageNew;
            if (null == album)
                getJSON("./" + albumName + ".json", loadAlbum, true, null);
            else if (0 == page)
                loadAlbumContent();
            else if (page > album.photos.length)
                error("Photo number out of range");
            else if (null == pages[page-1])
                getJSON(albumPath + album.metadataDir + album.photos[page-1].name + ".json", loadPhoto, true, {"page":page});
            else
                loadPhotoContent();
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }
    
    log("start exit");
}


// Check if the browser is known to not fire load events on link elements.
function brokenLoadEventOnLink()
{
    // Load events on link elements are broken on Android versions prior to 4.4
    regex = /Android ([0-9]+)\.([0-9]+)(?:[^0-9]|$)/i
    match = regex.exec(navigator.userAgent);
    if (null != match && 3 == match.length)
        return (match[1] < 4 || match[2] < 4)

    return false;
}


// Load the debug stylesheet and update links
function loadDebug()
{
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
    if (brokenLoadEventOnLink())
    {
        pollUntil(50, 6, function() {
                return document.styleSheets[document.styleSheets.length-1].href.endsWith("/debug.css");
            }, loadDebugAfterStylesheet, loadDebugError);
    }

    log("loadDebug exit");
}


// Update the page after the debug stylesheet has loaded
function loadDebugAfterStylesheet()
{
    log("loadDebugAfterStylesheet enter");

    try
    {
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
        for (var i=0; i<links.length; ++i)
            links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));

        // resume the load process, now that we have the debug document elements.
        start();
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadDebugAfterStylesheet exit");
}


// Leave debug mode due to failure of the debug stylesheet to load
function loadDebugError()
{
    log("loadDebugError enter");

    try
    {
        debug = false;

        // Unload the debug stylesheet
        var cssElement = document.getElementById("debugStylesheet");
        cssElement.parentNode.removeChild(cssElement);

        // Remove the debug tag from the URL
        window.location.hash = generatePhotoURL(page, false);
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadDebugError exit");
}


// Unload the debug stylesheet and update links
function unloadDebug()
{
    log("unloadDebug enter");

    // Unload the debug stylesheet
    var cssElement = document.getElementById("debugStylesheet");
    cssElement.parentNode.removeChild(cssElement);

    // Remove the debug panel
    var debugPanel = document.getElementById("debugPanel");
    debugPanel.parentNode.removeChild(debugPanel);

    // Remove the debug keyword from navivation links
    var links = document.querySelectorAll("a.navigationlink");
    for (var i=0; i<links.length; ++i)
        links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));

    // resume the load process, now that we've removed the debug document elements.
    start();

    log("unloadDebug exit");
}


// Load the album description, then use it to display the requested page
function loadAlbum(status, albumData, args)
{
    log("loadAlbum enter");

    if (200 != status)
        throw new Error("Album data is missing");
    else
    {
        verifyAlbum(albumData);
        album = albumData;
        // Now that we have the album loaded, set the keystroke handler
        document.addEventListener("keydown", keyHandler, false);
        if (0 == page)
            loadAlbumContent();
        else if (page > album.photos.length)
            throw new Error("Photo number out of range");
        else if (null == pages[page-1])
            getJSON(albumPath + album.metadataDir + album.photos[page-1].name + ".json", loadPhoto, true, {"page":page});
        else
            loadPhotoContent();
    }

    log("loadAlbum exit");
}


// Sanity-check the album description.  Error out if it's invalid.
function verifyAlbum(albumData)
{
    if ((null == albumData)
        || (null == albumData.title)
        || (null == albumData.footer)
        || (null == albumData.description)
        || (null == albumData.metadataDir)
        || (null == albumData.photos))
    {
        throw new Error("Album data is invalid");
        return;
    }
    for (i=0; i<albumData.photos.length; ++i)
    {
        if ((null == albumData.photos[i])
            || (null == albumData.photos[i].name)
            || (null == albumData.photos[i].thumbnail)
            || (null == albumData.photos[i].orientation))
        {
            throw new Error("Album data is invalid")
            return;
        }
    }
}


// Display the album contents
function loadAlbumContent()
{
    log("loadAlbumContent enter");

    document.getElementById("stylesheet").setAttribute("href", "album.css");

    // Set the title
    document.title = album.title;
    document.getElementById("titleContent").textContent = album.title;
    document.getElementById("footerContent").textContent = album.footer;
    document.getElementById("description").textContent = album.description;

    var listElement = document.getElementById("thumbnailList");
    while (null != listElement.firstChild)
        listElement.removeChild(listElement.firstChild);

    // Insert thumbnails as clones of a template
    var templateElement = document.createElement("li");
    templateElement.setAttribute("class", "thumbnail");
    var templateLinkElement = document.createElement("a");
    var templatePhotoElement = document.createElement("img");
    templatePhotoElement.setAttribute("alt", "Photo thumbnail");
    templateLinkElement.appendChild(templatePhotoElement);
    templateElement.appendChild(templateLinkElement);
    for (i=0; i<album.photos.length; ++i)
    {
        var itemElement = templateElement.cloneNode(true);
        var linkElement = itemElement.getElementsByTagName("a")[0];
        var photoElement = itemElement.getElementsByTagName("img")[0];
        linkElement.setAttribute("href", generatePhotoURL(i+1));
        linkElement.setAttribute("class", "navigationlink");
        linkElement.setAttribute("data-target", i+1);
        photoElement.setAttribute("src", albumPath + album.photos[i].thumbnail);
        if ("vertical" == album.photos[i].orientation)
            photoElement.setAttribute("class", "vthumbnail");
        else
            photoElement.setAttribute("class", "hthumbnail");
        listElement.appendChild(itemElement);
    }

    document.getElementById("indexLink").setAttribute("href", ".");
    if (debug)
        document.getElementById("debugLink").setAttribute("href", generatePhotoURL(0, true));

    cacheNext();

    log("loadAlbumContent exit");
}


// Load a photo description, then display the photo.
function loadPhoto(status, photoData, args)
{
    log("loadPhoto enter");

    if (200 != status)
        throw new Error("Photo data is missing");
    else
    {
        if (page == args.page)
        {
            verifyPhoto(photoData);
            pages[page-1] = photoData;
            loadPhotoContent();
        }
    }

    log("loadPhoto exit");
}


// Verify that a photo description is well-formed.
function verifyPhoto(photoData)
{
    if ((null == photoData)
        || (null == photoData.photo)
        || (null == photoData.width)
        || (null == photoData.height)
        || (null == photoData.properties)
        || (null == photoData.caption))
    {
        throw new Error("Photo data is invalid");
        return;
    }
}


// Display a photo and its description
function loadPhotoContent()
{
    log("loadPhotoContent enter");

    var photoData = pages[page-1];

    document.getElementById("photo").style["visibility"] = "hidden";

    // If we're not already using the photo stylesheet, the photo won't re-size 
    // properly unless we load the stylesheet first.  Chrome doesn't fire a 
    // load event when the target of a link element changes, so we need to 
    // create a new link element.
    var cssElement = document.getElementById("stylesheet");
    if ("photo.css" != cssElement.getAttribute("href"))
    {
        var cssElementNew = cssElement.cloneNode();
        cssElementNew.addEventListener("load", loadPhotoAfterStylesheet, false);
        cssElementNew.setAttribute("href", "photo.css");
        cssElement.parentNode.replaceChild(cssElementNew, cssElement);

        // Some browsers don't call load events on link objects.  So we need to 
        // poll until the stylesheet is present.
        if (brokenLoadEventOnLink())
        {
            pollUntil(50, 6, function() {
                    return document.styleSheets.length >= 2 && document.styleSheets[1].href.endsWith("/photo.css");
                }, loadPhotoAfterStylesheet, function() { error("Error loading stylesheet"); });
        }
    }
    else
        loadPhotoAfterStylesheet();

    // Set the title
    document.title = album.title + " (" + page + "/" + album.photos.length + ")";
    document.getElementById("titleContent").textContent = album.title;
    document.getElementById("footerContent").textContent = album.footer;

    // Set the photo index
    document.getElementById("index").textContent = page + "/" + album.photos.length;

    // Load photo caption
    var captionElement = document.getElementById("captionPanel");
    while (null != captionPanel.firstChild)
        captionPanel.removeChild(captionPanel.firstChild);
    for (idx in photoData.caption)
    {
        var captionElement = document.createElement("p");
        captionElement.setAttribute("class", "captionItem");
        captionElement.textContent = photoData.caption[idx];
        captionPanel.appendChild(captionElement);
    }

    // Load photo properties
    var propertyTable = document.getElementById("propertyTable");
    var rows = propertyTable.getElementsByTagName("tr");
    while (0 != rows.length)
        propertyTable.removeChild(rows[0]);
    for (idx in photoData.properties)
    {
        var rowElement = document.createElement("tr");
        var cellElement = document.createElement("td");
        cellElement.textContent = photoData.properties[idx][0];
        rowElement.appendChild(cellElement);

        cellElement = document.createElement("td");
        cellElement.textContent = photoData.properties[idx][1];
        rowElement.appendChild(cellElement);

        propertyTable.appendChild(rowElement);
    }

    if (1 == page)
    {
        // No previous photo
        document.getElementById("prevThumbPanel").style["visibility"] = "hidden";
        document.getElementById("prevImage").style["visibility"] = "hidden";
    }
    else
    {
        // Set the previous photo thumbnail
        var prevLinkElement = document.getElementById("prevThumbLink");
        prevLinkElement.setAttribute("href", generatePhotoURL(page-1));
        prevLinkElement.setAttribute("data-target", page-1);
        var prevThumbElement = document.getElementById("prevThumbImage");
        prevThumbElement.setAttribute("src", albumPath + album.photos[page-1-1].thumbnail);
        if ("vertical" == album.photos[page-1-1].orientation)
            prevThumbElement.setAttribute("class", "vnavigation");
        else
            prevThumbElement.setAttribute("class", "hnavigation");
        document.getElementById("prevThumbPanel").style["visibility"] = "visible";

        // Set the previous photo link
        prevLinkElement = document.getElementById("prevLink");
        prevLinkElement.setAttribute("href", generatePhotoURL(page-1));
        prevLinkElement.setAttribute("data-target", page-1);
        document.getElementById("prevImage").style["visibility"] = "visible";
    }

    if (page == album.photos.length)
    {
        // No next photo
        document.getElementById("nextThumbPanel").style["visibility"] = "hidden";
        document.getElementById("nextImage").style["visibility"] = "hidden";
    }
    else
    {
        // Set the next photo thumbnail
        var nextLinkElement = document.getElementById("nextThumbLink");
        nextLinkElement.setAttribute("href", generatePhotoURL(page+1));
        nextLinkElement.setAttribute("data-target", page+1);
        var nextThumbElement = document.getElementById("nextThumbImage");
        nextThumbElement.setAttribute("src", albumPath + album.photos[page-1+1].thumbnail);
        if ("vertical" == album.photos[page-1+1].orientation)
            nextThumbElement.setAttribute("class", "vnavigation");
        else
            nextThumbElement.setAttribute("class", "hnavigation");
        document.getElementById("nextThumbPanel").style["visibility"] = "visible";

        // Set the next photo link
        nextLinkElement = document.getElementById("nextLink");
        nextLinkElement.setAttribute("href", generatePhotoURL(page+1));
        nextLinkElement.setAttribute("data-target", page+1);
        document.getElementById("nextImage").style["visibility"] = "visible";
    }

    document.getElementById("indexLink").setAttribute("href", generatePhotoURL(0));
    if (debug)
        document.getElementById("debugLink").setAttribute("href", generatePhotoURL(page, true));

    cacheNext();

    log("loadPhotoContent exit");
}


// Display a photo
function loadPhotoAfterStylesheet()
{
    log("loadPhotoAfterStylesheet enter");

    try
    {
        if (0 < page)
        {
            // Load the photo.  Run "fitPhoto()" when it's ready.
            photoData = pages[page-1];
            var photoElement = document.getElementById("photo");
            // Remove the event listeners before we change anything so that we don't get fitPhoto storms in IE8
            photoElement.removeEventListener("load", fitPhoto, false);
            window.removeEventListener("resize", fitPhoto, false);
            // Webkit doesn't fire a load event if the src doesn't change.  So let's make sure it changes.
            photoElement.setAttribute("src", "");
            photoElement.style["width"] = photoData.width + "px";
            photoElement.style["height"] = photoData.height + "px"
            photoElement.addEventListener("load", fitPhoto, false);
            // Make sure that the event listener is in place before we set the photo
            photoElement.setAttribute("src", albumPath + photoData.photo);
            window.addEventListener("resize", fitPhoto, false);

            document.getElementById("photoOverlay").style["backgroundImage"] = "url(" + albumPath + photoData.photo + ")";
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("loadPhotoAfterStylesheet exit");
}


// Scale a photo to fit in its frame
function fitPhoto()
{
    log("fitPhoto enter");

    try
    {
        hidePhotoOverlay();
        hideHelp();

        if (0 < page)
        {
            var photoData = pages[page-1];
            var photo;          // the photo to be modified
            var photoAspect;    // the width/height aspect ratio of photo
            var photoPanel;     // the panel to hold the photo
            var photoBorder;    // the width of the border on photo, in pixels
            var panelWidth;     // the current width of photoPanel, in pixels
            var panelHeight;    // the current height of photoPanel, in pixels
            var panelAspect;    // the current aspect ratio of photoPanel
            var windowWidth;    // the width of the window
            var windowHeight;   // the height of the window
            var photoOverlay;   // the overlay photo

            photo = document.getElementById("photo");
            photoOverlay = document.getElementById("photoOverlay");
            photoAspect = photoData.width/photoData.height;
            photoPanel = document.getElementById("contentPanel");

            photoBorder = getVBorder(photo);
            panelWidth = getObjWidth(photoPanel) - getHBorder(photo);
            panelHeight = getObjHeight(photoPanel) - getVBorder(photo);
            panelAspect = panelWidth/panelHeight;

            windowWidth = (window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth) - 10;
            windowHeight = (window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight) - 10;

            // set the width and height of the photo
            if ((panelWidth >= photoData.width) && (panelHeight >= photoData.height))
            {
                // unconstrained
                photo.style["width"] = photoData.width + "px";
                photo.style["height"] = photoData.height + "px";
                photo.removeEventListener("click", showPhotoOverlay, false);
            }
            else if (photoAspect >= panelAspect)
            {
                // constrained by width
                photo.style["width"] = panelWidth + "px";
                photo.style["height"] = photoData.height*panelWidth/photoData.width + "px";
                photo.addEventListener("click", showPhotoOverlay, false);
                photoOverlay.style["width"] = Math.min(windowWidth, photoData.width) + "px";
                photoOverlay.style["height"] = Math.min((photoData.height*windowWidth/photoData.width), photoData.height) + "px";
            }
            else
            {
                // constrained by height
                photo.style["height"] = panelHeight + "px";
                photo.style["width"] = photoData.width*panelHeight/photoData.height + "px";
                photo.addEventListener("click", showPhotoOverlay, false);
                photoOverlay.style["height"] = Math.min(windowHeight, photoData.height) + "px";
                photoOverlay.style["width"] = Math.min((photoData.width*windowHeight/photoData.height), photoData.width) + "px";
            }

            photo.style["visibility"] = "visible";
            log("fitphoto: " + photo.style["height"] + " " + photo.style["width"]);
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }

    log("fitPhoto exit");
}


// Return a URL to a photo.
function generatePhotoURL(index, suppressDebug)
{
    var link = "#/" + encodeURIComponent(encodeURIComponent(albumName));
    if (null != index && 0 != index)
        link += "/" + index;
    if (debug && (true != suppressDebug))
        link += "/debug";
    return link;
}


// Fetch and cache the JSON for the next page
function cacheNext()
{
    log("cacheNext enter");

    if (null != page && page < album.photos.length && null == pages[page])
    {
        getJSON(albumPath + album.metadataDir + album.photos[page].name + ".json", cachePhoto, false, {"page" : page});
    }

    log("cacheNext exit");
}


// Cache a photo
function cachePhoto(status, photoData, args)
{
    log("cachePhoto enter");

    if (200 != req.status)
        throw new Error("Photo data is missing");
    else
    {
        if (null == pages[args.page])
        {
            verifyPhoto(photoData);
            pages[args.page] = photoData;
            var preload = new Image();
            preload.src = albumPath + photoData.photo;
        }
    }

    log("cachePhoto exit");
}


// Handle keystroke events
function keyHandler(e)
{
    try
    {
        if (helpVisible && (27 /*escape*/ == e.keyCode))
        {
            hideHelp();
            return false;
        }
        else if (0 < page)
        {
            // On a photo page
            if (overlayVisible && (27 /*escape*/ == e.keyCode))
            {
                hidePhotoOverlay();
                return false;
            }
            else if (13 /*enter*/ == e.keyCode)
            {
                if (overlayVisible)
                    hidePhotoOverlay();
                else if (!helpVisible)
                    document.getElementById("photo").click();
                return false;
            }
            else if ((34 /*page down*/ == e.keyCode) || (32 /*space*/ == e.keyCode))
            {
                if (album.photos.length != page)
                    document.location.href = generatePhotoURL(page+1);
                return false;
            }
            else if ((33 /*page up*/ == e.keyCode) || (8 /*backspace*/ == e.keyCode))
            {
                if (1 != page)
                    document.location.href = generatePhotoURL(page-1);
                return false;
            }
            else if ((36 /*home*/ == e.keyCode) || (27 /*escape*/ == e.keyCode))
            {
                document.location.href = generatePhotoURL(0);
                return false;
            }
        }
        else if (0 == page)
        {
            // On an album page
            if (!helpVisible && (13 /*enter*/ == e.keyCode))
            {
                document.location.href = generatePhotoURL(1);
                return false;
            }
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}


// Record the start of a touch
var currentX = null;
var currentY = null;
function touchStart(evt)
{
    try
    {
        currentX = parseInt(evt.touches[0].clientX);
        currentY = parseInt(evt.touches[0].clientY);
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}


// Determine if the touch that just ended was a left or right swipe, and if so, 
// change the photo being displayed.
function touchEnd(evt)
{
    try
    {
        var thresholdY = 40;
        var thresholdX = 100;

        var motionX = parseInt(evt.changedTouches[0].clientX) - currentX;
        var motionY = parseInt(evt.changedTouches[0].clientY) - currentY;

        if ((thresholdY > Math.abs(motionY)) && (thresholdX < Math.abs(motionX)))
        {
            if (0 > motionX)
            {
                if (0 < page && album.photos.length != page)
                    document.location.href = generatePhotoURL(page+1);
            }
            else
            {
                if (1 <= page)
                    document.location.href = generatePhotoURL(page-1);
            }
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}

// Show the full-screen photo overlay
function showPhotoOverlay()
{
    try
    {
        overlayVisible = true;
        var overlay = document.getElementById("overlay");
        overlay.style["display"] = "block";
        overlay.addEventListener("click", hidePhotoOverlay, false);
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}


// Hide the full-screen photo overlay
function hidePhotoOverlay()
{
    try
    {
        if (overlayVisible)
        {
            document.getElementById("overlay").style["display"] = "none";
            overlayVisible = false;
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}


// Show the full-screen help overlay
function showHelp()
{
    try
    {
        var help = document.getElementById("helpTextPanel");
        help.style["display"] = "block";
        help.addEventListener("click", hideHelp, false);

        // Displaying the help text may resize the window.  Delay setting helpVisible to ensure 
        // that the call to fitPhoto() on the initial resize doesn't immediately suppress help.
        setTimeout( function() { helpVisible = true; }, 50);
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}


// Hide the full-screen help overlay
function hideHelp()
{
    try
    {
        if (helpVisible)
        {
            document.getElementById("helpTextPanel").style["display"] = "none";
            helpVisible = false;
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
    }
}
