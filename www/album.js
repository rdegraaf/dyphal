/*************************************************
  album.js
  Version 3.0
  Copyright (c) Rennie deGraaf, 2005-2013.  All rights reserved.
  Last modified: 24 May 2013
 
  Scripts for DHTML photo album.
*************************************************/

/*
Design goals: 
  - Works in current major browsers (Firefox, Chrome, IE)
  - Not badly broken in recent (IE 8) and minor (Opera, Konqueror) browsers
  - Safari won't be tested because it's no longer available on Windows and I 
    don't have a Mac.
  - All style in CSS.  Changes to CSS should not require script changes.
  - All content in HTML or generated from photo properties.
  - Support CSP and other modern web security.
*/

// TODO: generation tool for JSON files
// TODO: look for and strip out unnecessary CSS
// TODO: test IE, write compat shims for IE 8
// TODO: get rid of "contents" div?  Better strategy for the sticky footer?
// TODO: Konqueror: text is too big
// TODO: center photo vertically?
// TODO: click on photo or press key to show photo at highest available resolution, overlayed over the page
// TODO: index of albums?
// TODO: double-scale the photo if the screen is big enough to fit it
// TODO: Is it a bug that the master stylesheet can be loaded after the debug stylesheet when switching to photo view from thumbnail view with debug enabled?
// TODO: use generatePhotoURL for index URLs as well

/*
Notes:
  - Need to HTML-encode all strings.  Does textContent support HTML entities?
*/

var debug=false;
var album=null; // object describing the current album
var page=null; // number of the current page, 0 for the album thumbnail view
var pages=[]; // objects describing all pages that have been retrieved.  Corresponds to album.photos.


// Set up event listeners
window.addEventListener("load", start, false);
window.addEventListener("hashchange", start, false);
document.addEventListener("DOMContentLoaded", function() {
    // Since JavaScript is clearly enabled, hide the warning as early as possible
    document.getElementById("warning").style["display"] = "none";
}, false);


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


// Called when the document loads.  Display the requested page.
function start()
{
    try
    {
        // Parse the page arguments
        var debugNew = false;
        var pageNew = 0;
        var args = window.location.hash.substring(1).split(",");
        for (i=0; i<args.length; ++i)
        {
            if (("debug" == args[i]) && (false == debugNew))
                debugNew = true;
            else if (/^[0-9]+$/.test(args[i]))
                pageNew = parseInt(args[i]);
            else if ("" != args[i])
                warning("Unrecognized or duplicate page argument: " + args[i])
        }

        if (debug != debugNew)
        {
            debug = debugNew;
            if (debugNew)
                loadDebug();
            else
                unloadDebug();
        }
    
        if (page != pageNew)
        {
            page = pageNew;
            if (null == album)
                getJSON("album.json", loadAlbum, true, null);
            else if (0 == page)
                loadAlbumContent();
            else if (page > album.photos.length)
                error("Photo number out of range");
            else if (null == pages[page-1])
                getJSON("./" +  album.photos[page-1].name + ".json", loadPhoto, true, {"page":page});
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
    document.getElementsByTagName("head")[0].appendChild(cssElement);

    // Create a link to leave debug mode
    var debugPanel = document.createElement("div");
    debugPanel.setAttribute("id", "debugPanel");
    var debugLink = document.createElement("a");
    debugLink.setAttribute("id", "debugLink");
    debugLink.setAttribute("href", "broken_link.html");
    debugLink.textContent = "Leave debug mode";
    debugPanel.appendChild(debugLink);
    document.getElementsByTagName("body")[0].appendChild(debugPanel);

    // Add the debug keyword to navigation links
    document.getElementById("indexLink").setAttribute("href", "#debug");
    var links = getElementsByClass("a", "navigationlink");
    for (var i=0; i<links.length; ++i)
        links[i].setAttribute("href", generatePhotoURL(links[i].getAttribute("data-target")));
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
    document.getElementById("indexLink").setAttribute("href", "#");
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
            getJSON("./" +  album.photos[page-1].name + ".json", loadPhoto, true, {"page":page});
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
    document.getElementById("titleContent").innerHTML = album.title;
    document.getElementById("footerContent").innerHTML = album.footer;

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
        photoElement.setAttribute("src", album.photos[i].thumbnail);
        if ("vertical" == album.photos[i].orientation)
            photoElement.setAttribute("class", "vthumbnail");
        else
            photoElement.setAttribute("class", "hthumbnail");
        listElement.appendChild(itemElement);
    }

    if (debug)
        document.getElementById("debugLink").setAttribute("href", "#");

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
        cssElement.parentNode.removeChild(cssElement);
        cssElement = document.createElement("link");
        cssElement.setAttribute("rel", "stylesheet");
        cssElement.setAttribute("href", "photo.css");
        cssElement.setAttribute("id", "stylesheet");
        cssElement.addEventListener("load", loadPhotoAfterStylesheet, false);
        document.getElementsByTagName("head")[0].appendChild(cssElement);
    }
    else
        loadPhotoAfterStylesheet();

    // Set the title
    document.title = album.title + " (" + page + "/" + album.photos.length + ")";
    document.getElementById("titleContent").innerHTML = album.title;
    document.getElementById("footerContent").innerHTML = album.footer;

    // Set the photo index
    document.getElementById("index").innerHTML = page + "/" + album.photos.length;

    // Load photo caption
    var captionElement = document.getElementById("captionPanel");
    while (null != captionPanel.firstChild)
        captionPanel.removeChild(captionPanel.firstChild);
    for (idx in photoData.caption)
    {
        var captionElement = document.createElement("div");
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
        var spanElement = document.createElement("span");
        spanElement.setAttribute("class", "property");
        spanElement.textContent = propName;
        cellElement.appendChild(spanElement);
        rowElement.appendChild(cellElement);

        cellElement = document.createElement("td");
        cellElement.textContent = photoData.properties[propName];
        rowElement.appendChild(cellElement);

        propertyTable.appendChild(rowElement);
    }

    if (debug)
        document.getElementById("debugLink").setAttribute("href", "#"+page);

    if (1 == page)
    {
        // No previous photo
        document.getElementById("prevThumbPanel").style["visibility"] = "hidden";
        document.getElementById("prevLink").style["visibility"] = "hidden";
    }
    else
    {
        // Set the previous photo thumbnail
        var prevLinkElement = document.getElementById("prevThumbLink");
        prevLinkElement.setAttribute("href", generatePhotoURL(page-1));
        prevLinkElement.setAttribute("data-target", page-1);
        var prevThumbElement = document.getElementById("prevThumbImage");
        prevThumbElement.setAttribute("src", album.photos[page-1-1].thumbnail);
        if ("vertical" == album.photos[page-1-1].orientation)
            prevThumbElement.setAttribute("class", "vnavigation");
        else
            prevThumbElement.setAttribute("class", "hnavigation");
        document.getElementById("prevThumbPanel").style["visibility"] = "visible";

        // Set the previous photo link
        prevLinkElement = document.getElementById("prevLink");
        prevLinkElement.setAttribute("href", generatePhotoURL(page-1));
        prevLinkElement.setAttribute("data-target", page-1);
        prevLinkElement.style["visibility"] = "visible";
    }
            
    if (page == album.photos.length)
    {
        // No next photo
        document.getElementById("nextThumbPanel").style["visibility"] = "hidden";
        document.getElementById("nextLink").style["visibility"] = "hidden";
    }
    else
    {
        // Set the next photo thumbnail
        var nextLinkElement = document.getElementById("nextThumbLink");
        nextLinkElement.setAttribute("href", generatePhotoURL(page+1));
        nextLinkElement.setAttribute("data-target", page+1);
        var nextThumbElement = document.getElementById("nextThumbImage");
        nextThumbElement.setAttribute("src", album.photos[page-1+1].thumbnail);
        if ("vertical" == album.photos[page-1+1].orientation)
            nextThumbElement.setAttribute("class", "vnavigation");
        else
            nextThumbElement.setAttribute("class", "hnavigation");
        document.getElementById("nextThumbPanel").style["visibility"] = "visible";

        // Set the next photo link
        nextLinkElement = document.getElementById("nextLink");
        nextLinkElement.setAttribute("href", generatePhotoURL(page+1));
        nextLinkElement.setAttribute("data-target", page+1);
        nextLinkElement.style["visibility"] = "visible";
    }
    
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
            photoElement.setAttribute("src", photoData.photo);
            photoElement.setAttribute("width", photoData.width);
            photoElement.setAttribute("height", photoData.height);
            photoElement.addEventListener("load", fitPhoto, false);
            window.addEventListener("resize", fitPhoto, false);
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
            
            photo = document.getElementById("photo");
            photoAspect = photoData.width/photoData.height;
            photoPanel = document.getElementById("contentPanel");

            photoBorder = getVBorder(photo);
            panelWidth = getObjWidth(photoPanel) - getHBorder(photo);
            panelHeight = getObjHeight(photoPanel) - getVBorder(photo);
            panelAspect = panelWidth/panelHeight;

            // set the width and height of the photo
            if (photoAspect >= panelAspect)
            {
                // constrained by width
                photo.width = Math.min(panelWidth, photoData.width);
                photo.height = Math.min((photoData.height*panelWidth/photoData.width), photoData.height);
            }
            else
            {
                // constrained by height
                photo.height = Math.min(panelHeight, photoData.height);
                photo.width = Math.min((photoData.width*panelHeight/photoData.height), photoData.width);
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
function generatePhotoURL(index)
{
    var link = "#" + index;
    if (debug)
        link += ",debug";
    return link;
}


// Fetch and cache the JSON for the next page
function cacheNext()
{
    if (null != page && page < album.photos.length && null == pages[page])
    {
        getJSON("./" +  album.photos[page].name + ".json", cachePhoto, false, {"page" : page});
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
            preload.src = photoData.photo;
        }
    }
}


// Handle keystroke events
function keyHandler(e)
{
    try
    {
        if (0 < page)
        {
            // On a photo page
            if (34 == e.keyCode) // page down
            {
                if (page != album.photos.length)
                    document.location.href = generatePhotoURL(page+1);
                return false;
            }
            else if (33 == e.keyCode) // page up
            {
                if (page != 1)
                    document.location.href = generatePhotoURL(page-1);
                return false;
            }
            else if (36 == e.keyCode) // home
            {
                document.location.href = "#" + (debug?"debug":"");
                return false;
            }
        }
        else if (0 == page)
        {
            // On an album page
            if (13 == e.keyCode) // enter
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

