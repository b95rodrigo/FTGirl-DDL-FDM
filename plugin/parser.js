var msBatchVideoParser = (function()
{
    function MsBatchVideoParser() {}

    MsBatchVideoParser.prototype = {
        parse: function(obj)
        {
            var url = String(obj.url);
            console.log("FTGirl DDL FDM: resolving source URL: " + url);

            return fgLaunchBridge(obj, ["resolve-source", url])
                .then(function(data)
                {
                    return fgPlaylistFromBridge(url, data);
                })
                .catch(function(error)
                {
                    console.log("FTGirl DDL FDM batch parser failed: " + error);
                    return Promise.reject({
                        error: "Failed to resolve source: " + error,
                        isParseError: true
                    });
                });
        },

        isSupportedSource: function(url)
        {
            return /^https:\/\/paste\.fitgirl-repacks\.site\//i.test(url) ||
                   /^https:\/\/(?:www\.)?fitgirl-repacks\.site\/[^?#]+/i.test(url);
        },

        supportedSourceCheckPriority: function()
        {
            return 0x7FFFFFFF;
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

    return new MsBatchVideoParser();
}());
