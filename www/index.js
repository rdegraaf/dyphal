var debug=false;

// Called when the document loads
function start()
{
    // Load the debug stylesheet if requested.
    debug = ("true" == getQueryParam("debug"));
    if (true == debug)
        loadDebug();
    
    // Sanity-check the photo data.  Error out if it's invalid.
    var error = false;
    if ((null == albumData)
        || (null == albumData.title)
        || (null == albumData.footer)
        || (null == albumData.photos))
    {
        error = true;
    }
    else
    {
        for (i=0; i<albumData.photos.length; ++i)
        {
            if ((null == albumData.photos[i])
                || (null == albumData.photos[i].name)
                || (null == albumData.photos[i].thumbnail)
                || (null == albumData.photos[i].orientation))
            {
                error = true;
                break;
            }
        }
    }
    
    if (error)
    {
        document.getElementById("warning").innerHTML = "Error: album.js is missing or invalid";
    }
    else
    {
        // We need to delete the warning element rather than hiding it because 
        // it still takes up space and messes up the position of the thumbnails.
        deleteObject(document.getElementById("thumbnailPanel"), document.getElementById("warning"));

        // Set the title
        document.title = albumData.title;
        document.getElementById("titleContent").innerHTML = albumData.title;
        document.getElementById("footerContent").innerHTML = albumData.footer;

        // Insert thumbnails as clones of the template
        var listElement = document.getElementById("thumbnailList");
        var templateElement = document.getElementById("thumbnailTemplate");
        listElement.removeChild(templateElement);
        templateElement.removeAttribute("id");
        for (i=0; i<albumData.photos.length; ++i)
        {
            var vertical = ("vertical" == albumData.photos[i].orientation);
            var itemElement = templateElement.cloneNode(true);
            var linkElement = itemElement.getElementsByTagName("a")[0];
            var photoElement = itemElement.getElementsByTagName("img")[0];
            linkElement.setAttribute("href", generatePhotoURL(albumData.photos[i].name));
            photoElement.setAttribute("src", albumData.photos[i].thumbnail);
            if (vertical)
            {
                photoElement.setAttribute("class", "vthumbnail");
            }
            listElement.appendChild(itemElement);
        }
    }
}
