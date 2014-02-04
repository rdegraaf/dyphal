/*
 * Code copied from aight.js, http://github.com/shawnbot/aight/
 * Written by Shawn Allen, Eli Grey, and others?
 *
 * From aight.js:
 *   Aight is a collection of JavaScript shims that make IE8 behave like a 
 *   modern browser (sans SVG).
 * 
 * From LICENSE:
 *   aight is public domain
 */

!window.addEventListener && (function (WindowPrototype, DocumentPrototype, ElementPrototype, addEventListener, removeEventListener, dispatchEvent, registry) {
    WindowPrototype[addEventListener] = DocumentPrototype[addEventListener] = ElementPrototype[addEventListener] = function (type, listener) {
                var target = this;
 
                registry.unshift([target, type, listener, function (event) {
                        event.currentTarget = target;
                        event.preventDefault = function () { event.returnValue = false };
                        event.stopPropagation = function () { event.cancelBubble = true };
                        event.target = event.srcElement || target;
 
                        listener.call(target, event);
                }]);
 
                this.attachEvent("on" + type, registry[0][3]);
        };
 
        WindowPrototype[removeEventListener] = DocumentPrototype[removeEventListener] = ElementPrototype[removeEventListener] = function (type, listener) {
                for (var index = 0, register; register = registry[index]; ++index) {
                        if (register[0] == this && register[1] == type && register[2] == listener) {
                                return this.detachEvent("on" + type, registry.splice(index, 1)[0][3]);
                        }
                }
        };
 
        WindowPrototype[dispatchEvent] = DocumentPrototype[dispatchEvent] = ElementPrototype[dispatchEvent] = function (eventObject) {
                return this.fireEvent("on" + eventObject.type, eventObject);
        };
})(Window.prototype, HTMLDocument.prototype, Element.prototype, "addEventListener", "removeEventListener", "dispatchEvent", []);
(function() {
    try {
        // from Eli Grey @ http://eligrey.com/blog/post/textcontent-in-ie8
        if (Object.defineProperty && Object.getOwnPropertyDescriptor &&
            Object.getOwnPropertyDescriptor(Element.prototype, "textContent") &&
            !Object.getOwnPropertyDescriptor(Element.prototype, "textContent").get) {
            var innerText = Object.getOwnPropertyDescriptor(Element.prototype, "innerText");
            Object.defineProperty(Element.prototype, "textContent", {
                // It won't work if you just drop in innerText.get
                // and innerText.set or the whole descriptor.
                get: function() {
                    return innerText.get.call(this)
                },
                set: function(x) {
                    return innerText.set.call(this, x)
                }
            });
        }
    } catch (e) {
        // bad Firefox
    }
})();
