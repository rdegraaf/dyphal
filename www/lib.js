/**
  Various library routines used by Dyphal.
  Copyright (c) Rennie deGraaf, 2005-2014.  All rights reserved.
*/

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
                {
                    var response;
                    if (req.response) // W3C
                        response = req.response;
                    else // MSIE
                        response = req.responseText;
                    callback(req.status, JSON.parse(response), args);
                }
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


// Poll 'test' with an exponential backoff starting with 'interval' milliseconds between attempts. 
// When it returns true, call 'action'.  If it fails 'maxtries' times, call 'error'.
function pollUntil(interval, maxtries, test, action, error)
{
    if (test())
        action();
    else if (maxtries > 0)
        setTimeout(function() { pollUntil(interval*2, maxtries-1, test, action, error); }, interval);
    else
        error();
}


// Convert a dashed-lowercase string to camelCase.
function camel(str)
{
    var newstr="";
    var state=0;
    for (var i=0; i<str.length; ++i)
    {
        if (0 == state)
        {
            if ('-' == str[i])
                state = 1;
            else
                newstr += str[i];
        }
        else
        {
            newstr += str[i].toUpperCase();
            state = 0;
        }
    }

    return newstr;
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
            return eval("document.defaultView.getComputedStyle(obj,null)." + camel(prop));
    }
    else if (window.getComputedStyle) // Konqueror
        return window.getComputedStyle(obj,null).getPropertyValue(prop);
    else if (obj.currentStyle) // MSIE
        return eval('obj.currentStyle.' + camel(prop));
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


// Add a suffix-match method to String.
String.prototype.endsWith = function(suffix) {
    var lastIndex = this.lastIndexOf(suffix);
    return (-1 != lastIndex) && (this.length == lastIndex + suffix.length);
}

