function fgLogPythonResult(result)
{
    if (result && result.errorOutput)
        console.log("FTGirl DDL FDM Python stderr: " + result.errorOutput);
}

function fgParseBridgeOutput(result)
{
    fgLogPythonResult(result);

    if (!result)
        throw new Error("Python bridge returned no result");

    var output = String(result.output || "").trim();
    if (!output)
        throw new Error("Python bridge returned empty output (exitCode=" + result.exitCode + ")");

    var lines = output.split(/\r?\n/);
    var data = null;
    for (var i = lines.length - 1; i >= 0; --i)
    {
        var line = lines[i].trim();
        if (!line || line.charAt(0) !== "{")
            continue;
        try
        {
            data = JSON.parse(line);
            break;
        }
        catch (e) {}
    }

    if (!data)
        throw new Error("Could not parse Python bridge JSON output");
    if (!data.ok)
        throw new Error(data.error || "Python bridge failed");
    return data;
}

function fgLaunchBridge(obj, args)
{
    var requestId = obj && obj.requestId ? obj.requestId : 0;
    var interactive = obj && obj.interactive ? true : false;

    return launchPythonScript(requestId, interactive, "python/fdm_bridge.py", args)
        .then(fgParseBridgeOutput);
}

function fgDecodeFilename(url)
{
    var filename = "download";
    try
    {
        var hashIndex = url.indexOf("#");
        if (hashIndex !== -1 && hashIndex + 1 < url.length)
            filename = url.substring(hashIndex + 1);
        else
        {
            var m = url.match(/\/([^\/?#]+)(?:[?#]|$)/);
            if (m && m[1])
                filename = m[1];
        }
        try { filename = decodeURIComponent(filename); } catch (e) {}
        filename = filename.replace(/[<>:"\/\\|?*]/g, "_");
        if (!filename)
            filename = "download";
        if (filename.length > 240)
            filename = filename.substring(0, 240);
    }
    catch (e)
    {
        filename = "download";
    }
    return filename;
}

function fgExtension(filename)
{
    var m = String(filename || "").match(/\.([A-Za-z0-9]{1,10})$/);
    return m ? m[1].toLowerCase() : "bin";
}

function fgStripExtension(filename, ext)
{
    if (!filename || !ext)
        return filename || "download";
    var suffix = "." + ext;
    if (filename.toLowerCase().slice(-suffix.length) === suffix)
        return filename.slice(0, -suffix.length);
    return filename;
}

function fgPlaylistFromBridge(sourceUrl, data)
{
    var entries = [];
    var items = data.items || [];
    for (var i = 0; i < items.length; ++i)
    {
        var item = items[i];
        if (!item || !item.source_url)
            continue;

        // FDM playlist entries are not final download URLs. According to the
        // mediaListParser API, each entry URL is passed to the single-media
        // parser (msParser). Therefore keep the FuckingFast *page* URL here;
        // msParser will resolve it to the signed/direct URL only when the user
        // actually starts that selected file.
        entries.push({
            _type: "url",
            url: item.source_url,
            title: item.filename || fgDecodeFilename(item.source_url)
        });
    }

    if (!entries.length)
        throw new Error("No FuckingFast page links were found");

    return {
        _type: "playlist",
        title: data.title || "FTGirl Download",
        webpage_url: sourceUrl,
        entries: entries,
        id: "ftgirl-ddl-fdm-" + Date.now()
    };
}
