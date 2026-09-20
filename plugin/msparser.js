var msParser = (function()
{
    function MsParser() {}

    MsParser.prototype = {
        parse: function(obj)
        {
            var url = String(obj.url);
            console.log("FTGirl DDL FDM: resolving single FuckingFast URL: " + url);

            return fgLaunchBridge(obj, ["resolve-one", url])
                .then(function(data)
                {
                    var items = data.items || [];
                    if (!items.length || !items[0].direct_url)
                        throw new Error("Direct link was not returned");

                    var item = items[0];
                    var filename = item.filename || fgDecodeFilename(url);
                    var ext = fgExtension(filename);
                    var title = fgStripExtension(filename, ext);
                    var directUrl = item.direct_url;

                    return {
                        title: title,
                        webpage_url: url,
                        formats: [{
                            url: directUrl,
                            protocol: directUrl.indexOf("https://") === 0 ? "https" : "http",
                            ext: ext,
                            format_id: "direct_download"
                        }]
                    };
                })
                .catch(function(error)
                {
                    console.log("FTGirl DDL FDM single parser failed: " + error);
                    return Promise.reject({
                        error: "Failed to resolve FuckingFast link: " + error,
                        isParseError: true
                    });
                });
        },

        isSupportedSource: function(url)
        {
            return /^https:\/\/(?:www\.)?fuckingfast\.co\/.+/i.test(url) && !/\/dl\//i.test(url);
        },

        supportedSourceCheckPriority: function()
        {
            return 0x7FFFFFFF - 1;
        },

        isPossiblySupportedSource: function(obj)
        {
            return false;
        },

        minIntevalBetweenQueryInfoDownloads: function()
        {
            return 300;
        }
    };

    return new MsParser();
}());
