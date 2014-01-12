/*************************************************
  album.js
  Version 3.0
  Copyright (c) Rennie deGraaf, 2005-2014.  All rights reserved.
  Last modified: 11 Jan 2014
 
  Scripts for DHTML photo album.
*************************************************/

/*
Design goals: 
  - Works in current major browsers (Firefox, Chrome, IE, Android)
  - Not badly broken in recent (IE 8) and minor (Opera, Konqueror) browsers
  - Safari won't be tested because it's no longer available on Windows and I 
    don't have a Mac.  Likewise, IOS won't be tested because I don't have an 
    iPhone.
  - All style in CSS.  Changes to CSS should not require script changes.
  - All content in HTML or generated from photo properties.
  - Support CSP and other modern web security.
*/

// TODO: generation tool for JSON files, scaled photos
// TODO: test IE, write compat shims for IE 8
// TODO: test Android
// TODO: index of albums?
// TODO: mobile stylesheet?
// TODO: gestures for navigation on mobile?
// TODO: rename index.html to album.html
// TODO: minifier?

// BUG: old page contents remain visible when a hash change results in a load error (WONTFIX)
// BUG: font is bigger than expected in Konqueror and Opera (WONTFIX)
// BUG: backspace doesn't work for navigation in Konqueror or Opera (WONTFIX)
// BUG: overlay doesn't work properly in Opera (WONTFIX)
// BUG: The error event doesn't fire if the debug stylesheet fails to load in Opera (WONTFIX)
// BUG: Setting the initial image src to placeholder.png results in failure to load the first photo 
//      loaded from album view in Opera (and possibly Chrome some of the time?).  Cloning the img 
//      node rather than modifying fixes the problem in Opera, but causes a CSP violation in Chrome.

var debug=false;
var albumName=null; // name of the current album
var albumPath=null;
var album=null; // object describing the current album
var page=null; // number of the current page, 0 for the album thumbnail view
var pages=[]; // objects describing all pages that have been retrieved.  Corresponds to album.photos.
var overlayVisible=false;
var helpVisible = false;


// Set up event listeners
window.addEventListener("load", start, false);
window.addEventListener("hashchange", start, false);
// Since JavaScript is clearly enabled, hide the warning as early as possible
document.addEventListener("DOMContentLoaded", suppressWarning, false);


// Display an error message in the warning panel
function error(msg)
{
    var warningPanel = document.getElementById("warning");
    warningPanel.textContent = msg;
    warningPanel.style["display"] = "block";
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
        var args = window.location.hash.substring(1).split(",");
        if ((1 > args.length) || (3 < args.length) || ("" == args[0]))
            throw new Error("Incorrect page arguments");
        albumNameNew = args[0];
        if ((2 == args.length) && ("debug" == args[1]))
            debugNew = true;
        else if (2 <= args.length)
        {
            if (/^[0-9]+$/.test(args[1]))
            {
                pageNew = parseInt(args[1])
                if ((3 == args.length) && ("debug" == args[2]))
                    debugNew = true;
                else if (3 <= args.length)
                    throw new Error("Incorrect page arguments");
            }
            else
                throw new Error("Incorrect page arguments");
        }

        if (debug != debugNew)
        {
            debug = debugNew;
            if (debugNew)
                loadDebug();
            else
                unloadDebug();
        }
        
        if (albumName != albumNameNew)
        {
            albumName = albumNameNew;
            albumPath = "./" + albumName.replace(/[^\/]+$/, '');
            album = null;
            page = null;
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
                getJSON(albumPath + album.photos[page-1].name + ".json", loadPhoto, true, {"page":page});
            else
                loadPhotoContent();
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }
}


// Load the debug stylesheet and update links
function loadDebug()
{
    // Load the debug stylesheet
    var cssElement = document.createElement("link");
    cssElement.setAttribute("rel", "stylesheet");
    cssElement.setAttribute("href", "debug.css");
    cssElement.setAttribute("id", "debugStylesheet");
    // We'll only update the links if the stylesheet loads correctly.
    cssElement.addEventListener("load", loadDebugAfterStylesheet, false);
    cssElement.addEventListener("error", loadDebugError, false);
    document.getElementsByTagName("head")[0].appendChild(cssElement);
}


// Update the page after the debug stylesheet has loaded
function loadDebugAfterStylesheet()
{
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
        var links = getElementsByClass("a", "navigationlink");
        for (var i=0; i<links.length; ++i)
            links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }
}


// Leave debug mode due to failure of the debug stylesheet to load
function loadDebugError()
{
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
}


// Unload the debug stylesheet and update links
function unloadDebug()
{
    // Unload the debug stylesheet
    var cssElement = document.getElementById("debugStylesheet");
    cssElement.parentNode.removeChild(cssElement);

    // Remove the debug panel
    var debugPanel = document.getElementById("debugPanel");
    debugPanel.parentNode.removeChild(debugPanel);

    // Remove the debug keyword from navivation links
    var links = getElementsByClass("a", "navigationlink");
    for (var i=0; i<links.length; ++i)
        links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));
}


// Load the album description, then use it to display the requested page
function loadAlbum(status, albumData, args)
{
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
            getJSON(albumPath + album.photos[page-1].name + ".json", loadPhoto, true, {"page":page});
        else
            loadPhotoContent();
    }
}


// Sanity-check the album description.  Error out if it's invalid.
function verifyAlbum(albumData)
{
    if ((null == albumData)
        || (null == albumData.title)
        || (null == albumData.footer)
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
}


// Load a photo description, then display the photo.
function loadPhoto(status, photoData, args)
{
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
        cssElementNew.setAttribute("href", "photo.css");
        cssElementNew.addEventListener("load", loadPhotoAfterStylesheet, false);
        cssElement.parentNode.replaceChild(cssElementNew, cssElement);
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
    for (propName in photoData.properties)
    {
        var rowElement = document.createElement("tr");
        var cellElement = document.createElement("td");
        cellElement.textContent = propName;
        rowElement.appendChild(cellElement);

        cellElement = document.createElement("td");
        cellElement.textContent = photoData.properties[propName];
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
}


// Display a photo
function loadPhotoAfterStylesheet()
{
    try
    {
        if (0 < page)
        {
            // Load the photo.  Run "fitPhoto()" when it's ready.
            photoData = pages[page-1];
            var photoElement = document.getElementById("photo");
            photoElement.setAttribute("src", albumPath + photoData.photo);
            photoElement.style["width"] = photoData.width + "px";
            photoElement.style["height"] = photoData.height + "px"
            photoElement.addEventListener("load", fitPhoto, false);
            window.addEventListener("resize", fitPhoto, false);
            
            // Apparently background-image is called backgroundImage to JavaScript?
            photoOverlay = document.getElementById("photoOverlay").style["backgroundImage"] = "url(" + albumPath + photoData.photo + ")";
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }
}


// Scale a photo to fit in its frame
function fitPhoto()
{
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
            
            windowWidth = (window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth) - 6;
            windowHeight = (window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight) - 6;

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
                photo.style["width"] = Math.min(panelWidth, photoData.width) + "px";
                photo.style["height"] = Math.min((photoData.height*panelWidth/photoData.width), photoData.height) + "px";
                photo.addEventListener("click", showPhotoOverlay, false);
                photoOverlay.style["width"] = Math.min(windowWidth, photoData.width) + "px";
                photoOverlay.style["height"] = Math.min((photoData.height*windowWidth/photoData.width), photoData.height) + "px";
            }
            else
            {
                // constrained by height
                photo.style["height"] = Math.min(panelHeight, photoData.height) + "px";
                photo.style["width"] = Math.min((photoData.width*panelHeight/photoData.height), photoData.width) + "px";
                photo.addEventListener("click", showPhotoOverlay, false);
                photoOverlay.style["height"] = Math.min(windowHeight, photoData.height) + "px";
                photoOverlay.style["width"] = Math.min((photoData.width*windowHeight/photoData.height), photoData.width) + "px";
            }

            photo.style["visibility"] = "visible";
        }
    }
    catch (e)
    {
        error(e.name + ": " + e.message);
        throw e;
    }
}


// Return a URL to a photo.
function generatePhotoURL(index, suppressDebug)
{
    var link = "#" + albumName;
    if (0 != index)
        link += "," + index;
    if (debug && (true != suppressDebug))
        link += ",debug";
    return link;
}


// Fetch and cache the JSON for the next page
function cacheNext()
{
    if (null != page && page < album.photos.length && null == pages[page])
    {
        getJSON(albumPath + album.photos[page].name + ".json", cachePhoto, false, {"page" : page});
    }
}


// Cache a photo's JSON 
function cachePhoto(status, photoData, args)
{
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
                if (page != album.photos.length)
                    document.location.href = generatePhotoURL(page+1);
                return false;
            }
            else if ((33 /*page up*/ == e.keyCode) || (8 /*backspace*/ == e.keyCode))
            {
                if (page != 1)
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
        helpVisible = true;
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
