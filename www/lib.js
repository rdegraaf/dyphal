/*************************************************
* lib.js
* Copyright (c) Rennie deGraaf, 2005-2013.  All rights reserved.
* Last modified: 24 May 2013
*
* Scripts for DHTML photo album
* Various library routines used by other scripts
*************************************************/

// Retrieves and parses a JSON object, then makes a callback with the result 
// and any supplied arguments.  Catches any exceptions thrown by the callback, 
// which can be treated as fatal errors or as warnings.
function getJSON(object, callback, fatalErrors, args)
{
    req = new XMLHttpRequest();
    req.open("GET", object, true);
    req.onreadystatechange = function() {
        try
        {
            if (4 == req.readyState)
            {
                if (200 != req.status)
                    callback(req.status, null, args);
                else
                    callback(req.status, JSON.parse(req.response), args);
            }
        }
        catch (e)
        {
            if (fatalErrors)
            {
                error(e.name + ": " + e.message);
                throw e;
            }
            else
                warning(e.name + ": " + e.message);
        }
    };
    req.send();
}

// returns all elements of a certain type (tag) and class
function getElementsByClass ( tag, classname )
{
    var objs = new Array();
    var all = document.getElementsByTagName(tag);
    for (var i=0; i<all.length; i++)
    {
        if (all[i].className == classname)
            objs[objs.length] = all[i];
    }
    return objs;
}

// gets a style property for an object
function getProperty ( obj, prop )
{
    // The eval() fallbacks will run afoul of CSP, but any browser that doesn't support 
    // getComputedStyle() properly probably doesn't support CSP anyway.
    if (document.defaultView && document.defaultView.getComputedStyle)
    {
        var val = document.defaultView.getComputedStyle(obj,null).getPropertyValue(prop)
        if (val)
            return val;
        else
            return eval("document.defaultView.getComputedStyle(obj,null)." + prop);
    }
    else if (window.getComputedStyle) // Konqueror
        return window.getComputedStyle(obj,null).getPropertyValue(prop);
    else if (obj.currentStyle) // MSIE
        return eval('obj.currentStyle.' + prop);
}

function getChildren ( obj )
{
    if (obj.children)
        return obj.children;
    
    var children = new Array();
    for (var i=0; i<obj.childNodes.length; i++)
    {
        if (obj.childNodes[i].nodeName.charAt(0) != '#')
            children[children.length] = obj.childNodes[i];
    }
    
    return children;
}

// gets the width of an object, in pixels
function getObjWidth ( obj )
{
    var w = getProperty(obj, "width");

    // find the begining of the number, after a space
    var a = w.indexOf(" ");
    if (a == -1)
        a = 0;
    // find the end of the number, before "px"
    var b = w.indexOf("px");
    
    if (b != -1)
        return parseInt(w.substr(a, b-a));
    else // value not returned in pixels
        return obj.clientWidth;
}
        
// gets the height of an object, in pixels
function getObjHeight ( obj )
{
    var w = getProperty(obj, "height");

    // find the begining of the number, after a space
    var a = w.indexOf(" ");
    if (a == -1)
        a = 0;
    // find the end of the number, before "px"
    var b = w.indexOf("px");
    
    if (b != -1)
        return parseInt(w.substr(a, b-a));
    else // value not returned in pixels
        return obj.clientHeight;
}
        
// gets the total width of all horizontal borders and padding of an object
function getHBorder ( obj )
{
    // this won't work if the units aren't pixels
    var leftBorder = parseInt(getProperty(obj, "border-left-width").replace(/[^0-9\.]/gi, ""));
    var leftPad = parseInt(getProperty(obj, "padding-left").replace(/[^0-9\.]/gi, ""));
    var rightPad = parseInt(getProperty(obj, "padding-right").replace(/[^0-9\.]/gi, ""));
    var rightBorder = parseInt(getProperty(obj, "border-right-width").replace(/[^0-9\.]/gi, ""));
            
    // assign a sane value if the unit wasn't in pixels
    if (isNaN(leftBorder))
        leftBorder = 0;
    if (isNaN(leftPad))
        leftPad = 0;
    if (isNaN(rightPad))
        rightPad = 0;
    if (isNaN(rightBorder))
        rightBorder = 0;
    
    return leftBorder + leftPad + rightPad + rightBorder;
}
        
// gets the total width of all vertical borders and padding of an object
function getVBorder ( obj )
{
    // this won't work if the units aren't pixels
    var topBorder = parseInt(getProperty(obj, "border-top-width").replace(/[^0-9\.]/gi, ""));
    var topPad = parseInt(getProperty(obj, "padding-top").replace(/[^0-9\.]/gi, ""));
    var bottomPad = parseInt(getProperty(obj, "padding-bottom").replace(/[^0-9\.]/gi, ""));
    var bottomBorder = parseInt(getProperty(obj, "border-bottom-width").replace(/[^0-9\.]/gi, ""));

    // assign a sane value if the unit wasn't in pixels
    if (isNaN(topBorder))
        topBorder = 0;
    if (isNaN(topPad))
        topPad = 0;
    if (isNaN(bottomPad))
        bottomPad = 0;
    if (isNaN(bottomBorder))
        bottomBorder = 0;
    
    return topBorder + topPad + bottomPad + bottomBorder;
}


