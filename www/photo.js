/*************************************************
  photo.js
  Copyright (c) Rennie deGraaf, 2005-2013.  All rights reserved.
  Last modified: 06 January 2013
 
  Scripts for photo display page of DHTML photo album.
*************************************************/

/*
Design goals: 
  - Works in current major browsers (Firefox, Chrome, IE)
  - Not badly broken in recent and minor (Opera, Konqueror) browsers
  - Safari won't be tested because it's no longer available on Windows and I 
    don't have a Mac.
  - All style in CSS.  Changes to CSS should not require script changes.
  - All content in HTML or generated from photo properties
*/

// TODO: version control
// TODO: generation tool for photoData files
// TODO: strip out unnecessary JS and CSS
// TODO: test with Safari, IE, and Opera
// TODO: test long index pages
// TODO: get rid of "contents" div in index.html?
// TODO: Konqueror: text is too big
// TODO: center photo vertically?
// TODO: insert properties & caption items as clones of a template?
// TODO: don't assume only one <a> and <img> in thumbnail template?

/*
Notes:
  - Need to escape names of all generated files (images, thumbnails, data).  
    cgi.escape() should do the trick.
  - Need escape double-quotes in strings
*/

var dataName=null;
var photoData={};
var debug=false;

// Called when the document loads
function start()
{
    // Load the debug stylesheet if requested.
    debug = ("true" == getQueryParam("debug"));
    if (true == debug)
        loadDebug();
    
    // Load the photo data script.  Run "loadContent()" when it's ready.
    dataName = getQueryParam("photo");
    if (null == dataName)
    {
        document.getElementById("warning").innerHTML="Error: query parameter 'photo' not found.";
    }
    else
    {
        // If the script doesn't exist, we'll never call loadContent().
        document.getElementById("warning").innerHTML="Error: data file not found for photo '"+dataName+"'.";
        var scriptElement = document.createElement("script");
        scriptElement.setAttribute("type", "text/javascript");
        scriptElement.setAttribute("src", "./"+dataName+".js");
        scriptElement.setAttribute("onload", "loadContent()");
        document.getElementsByTagName("head")[0].appendChild(scriptElement);
    }
}

// Called when the photo data file loads
function loadContent()
{
    // Sanity-check the photo data.  Error out if it's invalid.
    if ((null == photoData)
        || (null == photoData.photo)
        || (null == photoData.width)
        || (null == photoData.height)
        || (null == photoData.index)
        || (null == photoData.count)
        || (null == photoData.title)
        || (null == photoData.footer)
        || (("1" != photoData.index)
            && ((null == photoData.prev)
                || (null == photoData.prevThumb)
                || (null == photoData.prevThumbOrientation)))
        || ((photoData.count != photoData.index)
            && ((null == photoData.next)
                || (null == photoData.nextThumb)
                || (null == photoData.nextThumbOrientation)))
        || (null == photoData.properties)
        || (null == photoData.caption))
    {
        document.getElementById("warning").innerHTML = "Error: data file for photo '"+dataName+"' is missing required fields.";
    }
    else
    {
        // We need to delete the warning element rather than hiding it because 
        // it still takes up space and messes up the position of the photo.
        deleteObject(document.getElementById("photoPanel"), document.getElementById("warning"));
        
        // Load the photo.  Run "fitPhoto()" when it's ready.
    	var photoElement = document.getElementById("photo");
    	photoElement.setAttribute("src", photoData.photo);
        photoElement.setAttribute("width", photoData.width);
    	photoElement.setAttribute("height", photoData.height);
    	photoElement.setAttribute("onload", "fitPhoto()");
        
        // Set the title
        document.title = photoData.title + " (" + photoData.index + "/" + photoData.count + ")";
        document.getElementById("titleContent").innerHTML = photoData.title;
        document.getElementById("footerContent").innerHTML = photoData.footer;
        
        // Set the photo index
        document.getElementById("index").innerHTML = photoData.index + "/" + photoData.count;
        
        if (debug)
        {
            var indexLinkElement = document.getElementById("indexLink");
            indexLinkElement.setAttribute("href", indexLinkElement.getAttribute("href")+"?debug=true");
        }
        
        if ("1" == photoData.index)
        {
            // No previous photo
            document.getElementById("prevThumbPanel").style["visibility"] = "hidden";
            document.getElementById("prevLink").style["visibility"] = "hidden";
        }
        else
        {
            // Set the previous photo thumbnail
            var prevLinkElement = document.getElementById("prevThumbLink");
            prevLinkElement.setAttribute("href", generatePhotoURL(photoData.prev));
            var prevThumbElement = document.getElementById("prevThumbImage");
            prevThumbElement.setAttribute("src", photoData.prevThumb);
            if ("vertical" == photoData.prevThumbOrientation)
            {
                prevThumbElement.setAttribute("class", "vnavigation");
            }
            
            // Set the previous photo link
            prevLinkElement = document.getElementById("prevLink");
            prevLinkElement.setAttribute("href", generatePhotoURL(photoData.prev));
        }
            
        if (photoData.count == photoData.index)
        {
            // No next photo
            document.getElementById("nextThumbPanel").style["visibility"] = "hidden";
            document.getElementById("nextLink").style["visibility"] = "hidden";
        }
        else
        {
            // Set the next photo thumbnail
            var nextLinkElement = document.getElementById("nextThumbLink");
            nextLinkElement.setAttribute("href", generatePhotoURL(photoData.next));
            var nextThumbElement = document.getElementById("nextThumbImage");
            nextThumbElement.setAttribute("src", photoData.nextThumb);
            if ("vertical" == photoData.nextThumbOrientation)
            {
                nextThumbElement.setAttribute("class", "vnavigation");
            }

            // Set the next photo link
            nextLinkElement = document.getElementById("nextLink");
            nextLinkElement.setAttribute("href", generatePhotoURL(photoData.next));
        }
        
        // Load photo caption
        var captionElement = document.getElementById("captionPanel");
        for (idx in photoData.caption)
            insertCaptionItem(captionPanel, photoData.caption[idx]);

        // Load photo properties
        var propertyTable = document.getElementById("propertyTable");
        for (propName in photoData.properties)
            insertPropertyRow(propertyTable, propName, photoData.properties[propName]);
    }
}

// Called when the photo loads and when the window is resized
function fitPhoto()
{
    var photo;          // the photo to be modified
    var photoAspect;    // the width/height aspect ratio of photo
    var photoPanel;     // the panel to hold the photo
    var photoBorder;    // the width of the border on photo, in pixels
    var panelWidth;     // the current width of photoPanel, in pixels
    var panelHeight;    // the current height of photoPanel, in pixels
    var panelAspect;    // the current aspect ratio of photoPanel
    
    photo = document.getElementById("photo");
    photoAspect = photoData.width/photoData.height;
    photoPanel = document.getElementById("photoPanel");

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

// Insert a property row into a table.
function insertPropertyRow(tableElement, label, value)
{
    var rowElement = document.createElement("tr");
    var cellElement = document.createElement("td");
    var spanElement = document.createElement("span");
    spanElement.setAttribute("class", "property");
    spanElement.innerHTML = label;
    cellElement.appendChild(spanElement);
    rowElement.appendChild(cellElement);
    
    cellElement = document.createElement("td");
    cellElement.innerHTML = value;
    rowElement.appendChild(cellElement);
    
    tableElement.appendChild(rowElement);
}

// Insert a caption item into a container
function insertCaptionItem(containerElement, caption)
{
    var captionElement = document.createElement("div");
    captionElement.setAttribute("class", "captionItem");
    captionElement.innerHTML = caption;
    containerElement.appendChild(captionElement);
}
