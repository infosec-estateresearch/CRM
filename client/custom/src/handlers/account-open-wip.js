define([], function () {

    // "Open WIP / Revenue" on the Account detail page: opens the independent WIP
    // application's route for this firm in a new tab. Link only: no request is
    // made, nothing is stored, and no default address exists.

    var NOT_CONFIGURED = 'The WIP link is not configured.';
    var BAD_ID = 'The WIP link cannot be built for this record.';
    var FAILED = 'The WIP link could not be opened.';

    var ID_PATTERN = /^[A-Za-z0-9]+$/;

    // Returns the base without a single trailing slash, or null when the value
    // is not an absolute http(s) URL with a host and without user-info, query
    // or fragment.
    function checkedBase(value) {
        var url;

        if (typeof value !== 'string' || value === '') {
            return null;
        }

        try {
            url = new URL(value);
        } catch (e) {
            return null;
        }

        if (url.protocol !== 'http:' && url.protocol !== 'https:') {
            return null;
        }

        if (!url.host || !url.hostname) {
            return null;
        }

        if (url.username !== '' || url.password !== '') {
            return null;
        }

        if (url.search !== '' || url.hash !== '') {
            return null;
        }

        // URL() drops an empty "?" or "#"; the raw text must not carry them or
        // an "@" in the authority either.
        if (value.indexOf('?') !== -1 || value.indexOf('#') !== -1) {
            return null;
        }

        if (value.indexOf('@') !== -1) {
            return null;
        }

        if (value.charAt(value.length - 1) === '/') {
            return value.substring(0, value.length - 1);
        }

        return value;
    }

    function checkedId(id) {
        if (typeof id !== 'string' || id === '' || !ID_PATTERN.test(id)) {
            return null;
        }

        return id;
    }

    var Handler = function (view) {
        this.view = view;
    };

    Handler.prototype.warn = function (message) {
        try {
            Espo.Ui.warning(message);
        } catch (e) {
            // nothing else to do: the page must keep working
        }
    };

    Handler.prototype.openWip = function () {
        try {
            var id = checkedId(this.view.model.id);

            if (id === null) {
                this.warn(BAD_ID);

                return;
            }

            var base = checkedBase(this.view.getConfig().get('wipBaseUrl'));

            if (base === null) {
                this.warn(NOT_CONFIGURED);

                return;
            }

            var target = base + '/crm/firm/' + encodeURIComponent(id);

            var opened = window.open(target, '_blank', 'noopener,noreferrer');

            if (opened) {
                opened.opener = null;
            }
        } catch (e) {
            this.warn(FAILED);
        }
    };

    return Handler;
});
