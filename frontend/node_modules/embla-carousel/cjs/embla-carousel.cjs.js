'use strict';

function mapStoreToNumber(callback) {
  return input => {
    return callback(isNumber(input) ? input : input.get());
  };
}
function getSsrHandler(pluginList) {
  const ssrPlugin = pluginList.find(({
    name
  }) => name === 'ssr');
  return ssrPlugin;
}
function isNumber(subject) {
  return typeof subject === 'number';
}
function isString(subject) {
  return typeof subject === 'string';
}
function isObject(subject) {
  return Object.prototype.toString.call(subject) === '[object Object]';
}
function mathAbs(input) {
  return Math.abs(input);
}
function mathSign(input) {
  return Math.sign(input);
}
function deltaAbs(inputB, inputA) {
  return mathAbs(inputB - inputA);
}
function factorAbs(inputB, inputA) {
  if (inputB === 0 || inputA === 0) return 0;
  if (mathAbs(inputB) <= mathAbs(inputA)) return 0;
  const diff = deltaAbs(mathAbs(inputB), mathAbs(inputA));
  return mathAbs(diff / inputB);
}
function roundToTwoDecimals(input) {
  return Math.round(input * 100) / 100;
}
function arrayKeys(array) {
  return objectKeys(array).map(Number);
}
function arrayLast(array) {
  return array[arrayLastIndex(array)];
}
function arrayLastIndex(array) {
  return Math.max(0, array.length - 1);
}
function arrayIsLastIndex(array, index) {
  return index === arrayLastIndex(array);
}
function arrayFromRange(end, start = 0) {
  return Array.from(Array(end - start + 1), (_, index) => start + index);
}
function objectKeys(object) {
  return Object.keys(object);
}
function objectsMergeDeep(objectA, objectB) {
  return [objectA, objectB].reduce((mergedObjects, currentObject) => {
    objectKeys(currentObject).forEach(key => {
      const valueA = mergedObjects[key];
      const valueB = currentObject[key];
      const areObjects = isObject(valueA) && isObject(valueB);
      mergedObjects[key] = areObjects ? objectsMergeDeep(valueA, valueB) : valueB;
    });
    return mergedObjects;
  }, {});
}
function isMouseEvent(evt, ownerWindow) {
  return typeof ownerWindow.MouseEvent !== 'undefined' && evt instanceof ownerWindow.MouseEvent;
}

function Alignment(align, viewSize) {
  const predefined = {
    start,
    center,
    end
  };
  function start() {
    return 0;
  }
  function center(input) {
    return end(input) / 2;
  }
  function end(input) {
    return viewSize - input;
  }
  function measure(input, index) {
    if (isString(align)) return predefined[align](input);
    return align(viewSize, input, index);
  }
  const self = {
    measure
  };
  return self;
}

function EventStore() {
  let listeners = [];
  function add(node, type, handler, options = {
    passive: true
  }) {
    let removeListener;
    if ('addEventListener' in node) {
      node.addEventListener(type, handler, options);
      removeListener = () => node.removeEventListener(type, handler, options);
    } else {
      const legacyMediaQueryList = node;
      legacyMediaQueryList.addListener(handler);
      removeListener = () => legacyMediaQueryList.removeListener(handler);
    }
    listeners.push(removeListener);
    return self;
  }
  function clear() {
    listeners = listeners.filter(remove => remove());
  }
  const self = {
    add,
    clear
  };
  return self;
}

function Animations(update, render) {
  const documentVisibleHandler = EventStore();
  const fixedTimeStep = 1000 / 60;
  let windowInstance;
  let lastTimeStamp = null;
  let accumulatedTime = 0;
  let animationId = 0;
  function init(ownerWindow) {
    const ownerDocument = ownerWindow.document;
    windowInstance = ownerWindow;
    documentVisibleHandler.add(ownerDocument, 'visibilitychange', () => {
      if (ownerDocument.hidden) reset();
    });
  }
  function destroy() {
    stop();
    documentVisibleHandler.clear();
  }
  function animate(timeStamp) {
    if (!animationId) return;
    if (!lastTimeStamp) {
      lastTimeStamp = timeStamp;
      update();
      update();
    }
    const timeElapsed = timeStamp - lastTimeStamp;
    lastTimeStamp = timeStamp;
    accumulatedTime += timeElapsed;
    while (accumulatedTime >= fixedTimeStep) {
      update();
      accumulatedTime -= fixedTimeStep;
    }
    const alpha = accumulatedTime / fixedTimeStep;
    render(alpha);
    if (animationId) {
      animationId = windowInstance.requestAnimationFrame(animate);
    }
  }
  function start() {
    if (animationId) return;
    animationId = windowInstance.requestAnimationFrame(animate);
  }
  function stop() {
    if (!animationId) return;
    windowInstance.cancelAnimationFrame(animationId);
    lastTimeStamp = null;
    accumulatedTime = 0;
    animationId = 0;
  }
  function reset() {
    lastTimeStamp = null;
    accumulatedTime = 0;
  }
  const self = {
    init,
    destroy,
    start,
    stop,
    update,
    render
  };
  return self;
}

function Axis(axis, contentDirection) {
  const isRightToLeft = contentDirection === 'rtl';
  const isVertical = axis === 'y';
  const scroll = isVertical ? 'y' : 'x';
  const cross = isVertical ? 'x' : 'y';
  const sign = !isVertical && isRightToLeft ? -1 : 1;
  const startEdge = getStartEdge();
  const endEdge = getEndEdge();
  const nativeScroll = isVertical ? 'scrollTop' : 'scrollLeft';
  function getSize(nodeRect) {
    const {
      height,
      width
    } = nodeRect;
    return isVertical ? height : width;
  }
  function getStartEdge() {
    if (isVertical) return 'top';
    return isRightToLeft ? 'right' : 'left';
  }
  function getEndEdge() {
    if (isVertical) return 'bottom';
    return isRightToLeft ? 'left' : 'right';
  }
  function direction(input) {
    return input * sign;
  }
  const self = {
    scroll,
    cross,
    startEdge,
    endEdge,
    nativeScroll,
    getSize,
    direction: mapStoreToNumber(direction)
  };
  return self;
}

function Limit(min = 0, max = 0) {
  const length = mathAbs(min - max);
  function pastMinBound(input) {
    return input < min;
  }
  function pastMaxBound(input) {
    return input > max;
  }
  function pastAnyBound(input) {
    return pastMinBound(input) || pastMaxBound(input);
  }
  function clamp(input) {
    if (!pastAnyBound(input)) return input;
    return pastMinBound(input) ? min : max;
  }
  function removeOffset(input) {
    if (!length) return input;
    return input - length * Math.ceil((input - max) / length);
  }
  const self = {
    length,
    max,
    min,
    clamp: mapStoreToNumber(clamp),
    pastAnyBound: mapStoreToNumber(pastAnyBound),
    pastMaxBound: mapStoreToNumber(pastMaxBound),
    pastMinBound: mapStoreToNumber(pastMinBound),
    removeOffset: mapStoreToNumber(removeOffset)
  };
  return self;
}

function Counter(max, start, loop) {
  const {
    clamp
  } = Limit(0, max);
  const loopEnd = max + 1;
  let counter = normalize(start);
  function normalize(input) {
    return !loop ? clamp(input) : mathAbs((loopEnd + input) % loopEnd);
  }
  function get() {
    return counter;
  }
  function set(input) {
    counter = normalize(input);
    return self;
  }
  function add(input) {
    return clone().set(get() + input);
  }
  function clone() {
    return Counter(max, get(), loop);
  }
  const self = {
    get,
    set,
    add,
    clone
  };
  return self;
}

function DragHandler(active, axis, rootNode, target, dragTracker, location, animation, scrollTo, scrollBody, scrollTarget, indexCurrent, eventHandler, percentOfView, dragFree, dragThreshold, skipSnaps, baseFriction) {
  const {
    cross: crossAxis,
    direction
  } = axis;
  const focusNodes = ['INPUT', 'SELECT', 'TEXTAREA'];
  const nonPassiveEvent = {
    passive: false
  };
  const initEvents = EventStore();
  const mouseEvents = EventStore();
  const goToNextThreshold = Limit(50, 225).clamp(percentOfView.measure(20));
  const snapForceBoost = {
    mouse: 300,
    touch: 400
  };
  const freeForceBoost = {
    mouse: 500,
    touch: 600
  };
  const baseDuration = dragFree ? 43 : 25;
  let documentInstance;
  let windowInstance;
  let isMoving = false;
  let startScroll = 0;
  let startCross = 0;
  let runTouchEvents = false;
  let pointerIsDown = false;
  let preventScroll = false;
  let preventClick = false;
  let isMouse = false;
  function init(ownerWindow) {
    if (!active) return;
    documentInstance = ownerWindow.document;
    windowInstance = ownerWindow;
    dragTracker.init(ownerWindow);
    const node = rootNode;
    initEvents.add(node, 'dragstart', evt => evt.preventDefault(), nonPassiveEvent).add(node, 'touchmove', e => runTouchEvents && move(e), nonPassiveEvent).add(node, 'touchend', e => runTouchEvents && up(e)).add(node, 'touchstart', down).add(node, 'mousedown', down).add(node, 'touchcancel', up).add(node, 'contextmenu', up).add(node, 'click', click, true);
  }
  function destroy() {
    initEvents.clear();
    mouseEvents.clear();
    runTouchEvents = false;
  }
  function addMouseEvents() {
    const node = isMouse ? documentInstance : rootNode;
    mouseEvents.add(node, 'mousemove', move, nonPassiveEvent).add(node, 'mouseup', up);
  }
  function isFocusNode(node) {
    const nodeName = node.nodeName || '';
    return focusNodes.includes(nodeName);
  }
  function forceBoost() {
    const boost = dragFree ? freeForceBoost : snapForceBoost;
    const type = isMouse ? 'mouse' : 'touch';
    return boost[type];
  }
  function indexChanged() {
    const currentLocation = scrollTarget.byDistance(0, false);
    return currentLocation.index !== indexCurrent.get();
  }
  function baseForce(force) {
    return scrollTarget.byDistance(force, !dragFree).distance;
  }
  function allowedForce(force) {
    const next = indexCurrent.add(mathSign(force) * -1);
    if (dragFree || mathAbs(force) < goToNextThreshold) return baseForce(force);
    if (skipSnaps && indexChanged()) return baseForce(force) * 0.5;
    return scrollTarget.byIndex(next.get(), 0).distance;
  }
  function down(evt) {
    const event = eventHandler.createEvent('pointerdown', evt);
    const preventDefault = !event.emit();
    if (preventDefault) return;
    const isMouseEvt = isMouseEvent(evt, windowInstance);
    const isNotLeftButton = isMouseEvt && evt.button !== 0;
    isMouse = isMouseEvt;
    preventClick = dragFree && isMouseEvt && !evt.buttons && isMoving;
    isMoving = deltaAbs(target.get(), location.get()) >= 2;
    if (isNotLeftButton) return;
    if (isFocusNode(evt.target)) return;
    pointerIsDown = true;
    dragTracker.pointerDown(evt);
    scrollBody.useFriction(0).useDuration(0);
    target.set(location);
    startScroll = dragTracker.readPoint(evt);
    startCross = dragTracker.readPoint(evt, crossAxis);
    addMouseEvents();
    runTouchEvents = true;
  }
  function move(evt) {
    const event = eventHandler.createEvent('pointermove', evt);
    const preventDefault = !event.emit();
    if (preventDefault) return up(evt);
    const isTouchEvt = !isMouseEvent(evt, windowInstance);
    const isPinching = isTouchEvt && evt.touches.length >= 2;
    if (isPinching) return up(evt);
    const lastScroll = dragTracker.readPoint(evt);
    const lastCross = dragTracker.readPoint(evt, crossAxis);
    const diffScroll = deltaAbs(lastScroll, startScroll);
    const diffCross = deltaAbs(lastCross, startCross);
    if (!preventScroll && !isMouse) {
      if (!evt.cancelable) return up(evt);
      preventScroll = diffScroll > diffCross;
      if (!preventScroll) return up(evt);
    }
    const diff = dragTracker.pointerMove(evt);
    if (diffScroll > dragThreshold) preventClick = true;
    scrollBody.useFriction(0.3).useDuration(0.75);
    animation.start();
    target.add(direction(diff));
    if (evt.cancelable) evt.preventDefault();
  }
  function up(evt) {
    const event = eventHandler.createEvent('pointerup', evt);
    const rawForce = dragTracker.pointerUp(evt) * forceBoost();
    const force = allowedForce(direction(rawForce));
    const forceFactor = factorAbs(rawForce, force);
    const duration = baseDuration - 10 * forceFactor;
    const friction = baseFriction + forceFactor / 50;
    preventScroll = false;
    pointerIsDown = false;
    runTouchEvents = false;
    isMouse = false;
    mouseEvents.clear();
    scrollBody.useDuration(duration).useFriction(friction);
    scrollTo.distance(force, !dragFree);
    event.emit();
  }
  function click(evt) {
    if (preventClick) {
      evt.stopPropagation();
      evt.preventDefault();
      preventClick = false;
    }
  }
  function pointerDown() {
    return pointerIsDown;
  }
  const self = {
    init,
    destroy,
    pointerDown
  };
  return self;
}

function DragTracker(axis) {
  const logInterval = 170;
  let windowInstance;
  let startEvent;
  let lastEvent;
  function init(ownerWindow) {
    windowInstance = ownerWindow;
  }
  function readTime(evt) {
    return evt.timeStamp;
  }
  function readPoint(evt, evtAxis) {
    const property = evtAxis || axis.scroll;
    const coord = `client${property === 'x' ? 'X' : 'Y'}`;
    return (isMouseEvent(evt, windowInstance) ? evt : evt.touches[0])[coord];
  }
  function pointerDown(evt) {
    startEvent = evt;
    lastEvent = evt;
    return readPoint(evt);
  }
  function pointerMove(evt) {
    const diff = readPoint(evt) - readPoint(lastEvent);
    const expired = readTime(evt) - readTime(startEvent) > logInterval;
    lastEvent = evt;
    if (expired) startEvent = evt;
    return diff;
  }
  function pointerUp(evt) {
    if (!startEvent || !lastEvent) return 0;
    const diffDrag = readPoint(lastEvent) - readPoint(startEvent);
    const diffTime = readTime(evt) - readTime(startEvent);
    const expired = readTime(evt) - readTime(lastEvent) > logInterval;
    const force = diffDrag / diffTime;
    const isFlick = diffTime && !expired && mathAbs(force) > 0.1;
    return isFlick ? force : 0;
  }
  const self = {
    init,
    pointerDown,
    pointerMove,
    pointerUp,
    readPoint
  };
  return self;
}

function PercentOfView(viewSize) {
  function measure(input) {
    return viewSize * (input / 100);
  }
  const self = {
    measure
  };
  return self;
}

function ResizeHandler(active, container, eventHandler, slides, axis, nodeHandler) {
  const observeNodes = [container, ...slides];
  let resizeObserver;
  let containerSize;
  let slideSizes = [];
  let destroyed = false;
  function readSize(node) {
    return axis.getSize(nodeHandler.getRect(node));
  }
  function init(ownerWindow) {
    if (!active) return;
    containerSize = readSize(container);
    slideSizes = slides.map(readSize);
    resizeObserver = new ownerWindow.ResizeObserver(onResize);
    ownerWindow.requestAnimationFrame(() => {
      observeNodes.forEach(node => resizeObserver.observe(node));
    });
  }
  function destroy() {
    destroyed = true;
    if (resizeObserver) resizeObserver.disconnect();
  }
  function onResize(entries) {
    const event = eventHandler.createEvent('resize', entries);
    const preventDefault = !event.emit();
    if (preventDefault) return;
    for (const entry of entries) {
      if (destroyed) return;
      const isContainer = entry.target === container;
      const slideIndex = slides.indexOf(entry.target);
      const lastSize = isContainer ? containerSize : slideSizes[slideIndex];
      const newSize = readSize(isContainer ? container : slides[slideIndex]);
      const diffSize = mathAbs(newSize - lastSize);
      if (diffSize >= 0.5) {
        event.api.reInit();
        break;
      }
    }
  }
  const self = {
    init,
    destroy
  };
  return self;
}

function ScrollAnimator() {
  function update(engine) {
    const {
      dragHandler,
      scrollBody,
      scrollBounds,
      options: {
        loop
      }
    } = engine;
    if (!loop) scrollBounds.constrain(dragHandler.pointerDown());
    scrollBody.seek();
  }
  function render(engine, alpha) {
    const {
      scrollBody,
      translate,
      location,
      offsetLocation,
      previousLocation,
      scrollLooper,
      slideLooper,
      dragHandler,
      animation,
      eventHandler,
      scrollBounds,
      options: {
        loop
      }
    } = engine;
    const isIdle = scrollBody.settled();
    const isWithinBounds = !scrollBounds.shouldConstrain();
    const isPointerDown = dragHandler.pointerDown();
    const canSettle = loop || isWithinBounds;
    const isIdleAndCanSettle = isIdle && canSettle;
    const isScrolling = !isIdleAndCanSettle;
    const isDragging = isScrolling && isPointerDown;
    const isSettled = isIdleAndCanSettle && !isPointerDown;
    if (isSettled) {
      animation.stop();
    }
    const interpolatedLocation = location.get() * alpha + previousLocation.get() * (1 - alpha);
    offsetLocation.set(interpolatedLocation);
    if (loop) {
      scrollLooper.loop(scrollBody.direction());
      slideLooper.loop();
    }
    translate.to(offsetLocation);
    if (isSettled) {
      const event = eventHandler.createEvent('settle', null);
      event.emit();
    }
    if (isScrolling) {
      const event = eventHandler.createEvent('scroll', {
        isDragging
      });
      event.emit();
    }
  }
  const self = {
    update,
    render
  };
  return self;
}

function ScrollBody(location, offsetLocation, previousLocation, target, baseDuration, baseFriction) {
  let scrollVelocity = 0;
  let scrollDirection = 0;
  let scrollDuration = baseDuration;
  let scrollFriction = baseFriction;
  let rawLocation = location.get();
  let rawLocationPrevious = 0;
  function seek() {
    const displacement = target.minus(location);
    const isInstant = !scrollDuration;
    let scrollDistance = 0;
    if (isInstant) {
      scrollVelocity = 0;
      previousLocation.set(target);
      location.set(target);
      scrollDistance = displacement;
    } else {
      previousLocation.set(location);
      scrollVelocity += displacement / scrollDuration;
      scrollVelocity *= scrollFriction;
      rawLocation += scrollVelocity;
      location.add(scrollVelocity);
      scrollDistance = rawLocation - rawLocationPrevious;
    }
    scrollDirection = mathSign(scrollDistance);
    rawLocationPrevious = rawLocation;
    return self;
  }
  function settled() {
    const displacement = target.minus(offsetLocation);
    return mathAbs(displacement) < 0.001;
  }
  function duration() {
    return scrollDuration;
  }
  function direction() {
    return scrollDirection;
  }
  function velocity() {
    return scrollVelocity;
  }
  function useBaseDuration() {
    return useDuration(baseDuration);
  }
  function useBaseFriction() {
    return useFriction(baseFriction);
  }
  function useDuration(input) {
    scrollDuration = input;
    return self;
  }
  function useFriction(input) {
    scrollFriction = input;
    return self;
  }
  const self = {
    direction,
    duration,
    velocity,
    seek,
    settled,
    useBaseFriction,
    useBaseDuration,
    useFriction,
    useDuration
  };
  return self;
}

function ScrollBounds(limit, location, target, scrollBody, percentOfView) {
  const {
    pastAnyBound,
    pastMinBound,
    clamp
  } = limit;
  const pullBackThreshold = percentOfView.measure(10);
  const edgeOffsetTolerance = percentOfView.measure(50);
  const frictionLimit = Limit(0.1, 0.99);
  let disabled = false;
  function shouldConstrain() {
    if (disabled) return false;
    if (!pastAnyBound(target)) return false;
    if (!pastAnyBound(location)) return false;
    return true;
  }
  function constrain(pointerDown) {
    if (!shouldConstrain()) return;
    const edge = pastMinBound(location) ? 'min' : 'max';
    const diffToEdge = mathAbs(limit[edge] - location.get());
    const displacement = target.minus(location);
    const friction = frictionLimit.clamp(diffToEdge / edgeOffsetTolerance);
    target.subtract(displacement * friction);
    if (!pointerDown && mathAbs(displacement) < pullBackThreshold) {
      target.set(clamp(target));
      scrollBody.useDuration(25).useBaseFriction();
    }
  }
  function toggleActive(active) {
    disabled = !active;
  }
  const self = {
    shouldConstrain,
    constrain,
    toggleActive
  };
  return self;
}

function ScrollContain(viewSize, contentSize, snapsAligned, containScroll, pixelTolerance) {
  const scrollBounds = Limit(-contentSize + viewSize, 0);
  const snapsBounded = getSnapsBounded();
  const scrollContainLimit = getScrollContainLimit();
  const snapsContained = getSnapsContained();
  function usePixelTolerance(bound, snap) {
    return pixelTolerance ? deltaAbs(bound, snap) <= 1 : false;
  }
  function getScrollContainLimit() {
    const startSnap = snapsBounded[0];
    const endSnap = arrayLast(snapsBounded);
    const min = snapsBounded.lastIndexOf(startSnap);
    const max = snapsBounded.indexOf(endSnap) + 1;
    return Limit(min, max);
  }
  function getSnapsBounded() {
    return snapsAligned.map((snapAligned, index) => {
      const {
        min,
        max
      } = scrollBounds;
      const snap = scrollBounds.clamp(snapAligned);
      const isFirst = !index;
      const isLast = arrayIsLastIndex(snapsAligned, index);
      if (isFirst) return max;
      if (isLast) return min;
      if (usePixelTolerance(min, snap)) return min;
      if (usePixelTolerance(max, snap)) return max;
      return snap;
    }).map(scrollBound => parseFloat(scrollBound.toFixed(3)));
  }
  function getSnapsContained() {
    if (contentSize <= viewSize + pixelTolerance) return [scrollBounds.max];
    if (containScroll === 'keepSnaps') return snapsBounded;
    const {
      min,
      max
    } = scrollContainLimit;
    return snapsBounded.slice(min, max);
  }
  const self = {
    snapsContained,
    scrollContainLimit
  };
  return self;
}

function ScrollLimit(contentSize, scrollSnaps, loop) {
  const max = scrollSnaps[0];
  const min = loop ? max - contentSize : arrayLast(scrollSnaps);
  const limit = Limit(min, max);
  const self = {
    limit
  };
  return self;
}

function ScrollLooper(contentSize, limit, location, loopEntities) {
  const jointSafety = 0.1;
  const min = limit.min + jointSafety;
  const max = limit.max + jointSafety;
  const {
    pastMinBound,
    pastMaxBound
  } = Limit(min, max);
  function shouldLoop(direction) {
    if (direction === 1) return pastMaxBound(location);
    if (direction === -1) return pastMinBound(location);
    return false;
  }
  function loop(direction) {
    if (!shouldLoop(direction)) return;
    const loopDistance = contentSize * (direction * -1);
    loopEntities.forEach(loopEntity => loopEntity.add(loopDistance));
  }
  const self = {
    loop
  };
  return self;
}

function ScrollProgress(limit) {
  const {
    max,
    length
  } = limit;
  function get(input) {
    const currentLocation = input - max;
    return length ? currentLocation / -length : 0;
  }
  const self = {
    get: mapStoreToNumber(get)
  };
  return self;
}

function ScrollSnaps(axis, alignment, containerRect, slideRects, slidesToScroll) {
  const {
    startEdge,
    endEdge
  } = axis;
  const {
    groupSlides
  } = slidesToScroll;
  const alignments = measureSizes().map(alignment.measure);
  const snaps = measureUnaligned();
  const snapsAligned = measureAligned();
  function measureSizes() {
    return groupSlides(slideRects).map(rects => arrayLast(rects)[endEdge] - rects[0][startEdge]).map(mathAbs);
  }
  function measureUnaligned() {
    return slideRects.map(rect => containerRect[startEdge] - rect[startEdge]).map(snap => -mathAbs(snap));
  }
  function measureAligned() {
    return groupSlides(snaps).map(g => g[0]).map((snap, index) => snap + alignments[index]);
  }
  const self = {
    snaps,
    snapsAligned
  };
  return self;
}

function ScrollSnapList(containSnaps, containScroll, scrollSnaps, scrollContainLimit, slidesToScroll, slideIndexes, scrollProgress) {
  const {
    groupSlides
  } = slidesToScroll;
  const {
    min,
    max
  } = scrollContainLimit;
  const slidesBySnap = getSlidesBySnap();
  const snapBySlide = getSnapsBySlide();
  const progressBySnap = scrollSnaps.map(scrollProgress.get);
  const length = scrollSnaps.length;
  function getSlidesBySnap() {
    const groupedSlideIndexes = groupSlides(slideIndexes);
    const doNotContain = !containSnaps || containScroll === 'keepSnaps';
    if (scrollSnaps.length === 1) return [slideIndexes];
    if (doNotContain) return groupedSlideIndexes;
    return groupedSlideIndexes.slice(min, max).map((group, index, groups) => {
      const isFirst = !index;
      const isLast = arrayIsLastIndex(groups, index);
      if (isFirst) {
        const rangeEnd = arrayLast(group);
        return arrayFromRange(rangeEnd);
      }
      if (isLast) {
        const rangeEnd = arrayLastIndex(slideIndexes);
        return arrayFromRange(rangeEnd, group[0]);
      }
      return group;
    });
  }
  function getSnapsBySlide() {
    const snapBySlide = {};
    slidesBySnap.forEach((slideGroup, snapIndex) => {
      slideGroup.forEach(slideIndex => {
        snapBySlide[slideIndex] = snapIndex;
      });
    });
    return snapBySlide;
  }
  const self = {
    slidesBySnap,
    snapBySlide,
    progressBySnap,
    length
  };
  return self;
}

function ScrollTarget(loop, scrollSnaps, contentSize, limit, targetVector) {
  const {
    pastAnyBound,
    removeOffset,
    clamp
  } = limit;
  function minDistance(distances) {
    return distances.sort((a, b) => mathAbs(a) - mathAbs(b))[0];
  }
  function getClosestSnap(target) {
    const distance = loop ? removeOffset(target) : clamp(target);
    const {
      index
    } = scrollSnaps.reduce((result, snap, snapIndex) => {
      const displacementAbs = mathAbs(shortcut(snap - distance, 0));
      if (displacementAbs >= result.smallestDisplacement) return result;
      return {
        smallestDisplacement: displacementAbs,
        index: snapIndex
      };
    }, {
      smallestDisplacement: Infinity,
      index: 0
    });
    return {
      index,
      distance
    };
  }
  function shortcut(target, direction) {
    if (!loop) return target;
    const targets = [target, target + contentSize, target - contentSize];
    if (!direction) return minDistance(targets);
    const validTargets = targets.filter(t => mathSign(t) === direction);
    if (validTargets.length) return minDistance(validTargets);
    return arrayLast(targets) - contentSize;
  }
  function byIndex(index, direction) {
    const diffToSnap = scrollSnaps[index] - targetVector.get();
    const distance = shortcut(diffToSnap, direction);
    return {
      index,
      distance
    };
  }
  function byDistance(distance, snapToClosest) {
    const target = targetVector.plus(distance);
    const {
      index,
      distance: targetSnapDistance
    } = getClosestSnap(target);
    const isPastAnyBound = !loop && pastAnyBound(target);
    if (!snapToClosest || isPastAnyBound) return {
      index,
      distance
    };
    const diffToSnap = scrollSnaps[index] - targetSnapDistance;
    const snapDistance = distance + shortcut(diffToSnap, 0);
    return {
      index,
      distance: snapDistance
    };
  }
  const self = {
    byDistance,
    byIndex,
    shortcut
  };
  return self;
}

function ScrollTo(animation, indexCurrent, indexPrevious, scrollBody, scrollTarget, targetVector, eventHandler) {
  function scrollTo(target) {
    const {
      index: targetSnap,
      distance: targetDisplacement
    } = target;
    const sourceSnap = indexCurrent.get();
    const hasIndexChanged = targetSnap !== sourceSnap;
    if (targetDisplacement) {
      targetVector.add(targetDisplacement);
      if (scrollBody.duration()) {
        animation.start();
      } else {
        animation.update();
        animation.render(1);
        animation.update();
      }
    }
    if (hasIndexChanged) {
      indexPrevious.set(sourceSnap);
      indexCurrent.set(targetSnap);
      const event = eventHandler.createEvent('select', {
        targetSnap,
        sourceSnap
      });
      event.emit();
    }
  }
  function distance(input, snapToClosest) {
    const target = scrollTarget.byDistance(input, snapToClosest);
    scrollTo(target);
  }
  function index(input, direction) {
    const targetIndex = indexCurrent.clone().set(input).get();
    const target = scrollTarget.byIndex(targetIndex, getDirection(direction));
    scrollTo(target);
  }
  function getDirection(direction) {
    if (!direction) return 0;
    if (isNumber(direction)) return direction;
    return direction === 'forward' ? -1 : 1;
  }
  const self = {
    distance,
    index
  };
  return self;
}

function SlideFocus(axis, active, root, slides, scrollSnapList, scrollTo, scrollBody, eventStore, eventHandler) {
  const focusListenerOptions = {
    passive: true,
    capture: true
  };
  let lastTabPressTime = 0;
  function init(ownerWindow) {
    if (!active) return;
    eventStore.add(ownerWindow.document, 'keydown', onKeyDown, false);
    slides.forEach((slide, slideIndex) => {
      eventStore.add(slide, 'focus', evt => onFocus(evt, slideIndex), focusListenerOptions);
    });
  }
  function onFocus(evt, slideIndex) {
    const nowTime = new Date().getTime();
    const diffTime = nowTime - lastTabPressTime;
    if (diffTime > 10) return;
    const event = eventHandler.createEvent('slidefocus', evt);
    const preventDefault = !event.emit();
    if (preventDefault) return;
    root[axis.nativeScroll] = 0;
    const snapIndex = scrollSnapList.snapBySlide[slideIndex];
    if (!isNumber(snapIndex)) return;
    scrollBody.useDuration(0);
    scrollTo.index(snapIndex, 0);
  }
  function onKeyDown(event) {
    if (event.code === 'Tab') lastTabPressTime = new Date().getTime();
  }
  const self = {
    init
  };
  return self;
}

function NumberStore(initialValue) {
  let value = initialValue || 0;
  function get() {
    return value;
  }
  function set(input) {
    value = input;
  }
  function add(input) {
    value += input;
  }
  function subtract(input) {
    add(-input);
  }
  function plus(input) {
    return value + input;
  }
  function minus(input) {
    return plus(-input);
  }
  const self = {
    get,
    set: mapStoreToNumber(set),
    add: mapStoreToNumber(add),
    subtract: mapStoreToNumber(subtract),
    plus: mapStoreToNumber(plus),
    minus: mapStoreToNumber(minus)
  };
  return self;
}

function SlideLooper(viewSize, contentSize, slideSizes, slideSizesWithGaps, snaps, scrollSnaps, location, slideTranslates) {
  const roundingSafety = 0.5;
  const ascItems = arrayKeys(slideSizesWithGaps);
  const descItems = arrayKeys(slideSizesWithGaps).reverse();
  const loopPoints = startPoints().concat(endPoints());
  function getRemainingGapAfterSlides(indexes, from) {
    return indexes.reduce((remainingGap, index) => {
      return remainingGap - slideSizesWithGaps[index];
    }, from);
  }
  function getSlidesThatFitGap(indexes, gap) {
    return indexes.reduce((slidesThatFit, index) => {
      const remainingGap = getRemainingGapAfterSlides(slidesThatFit, gap);
      return remainingGap > 0 ? [...slidesThatFit, index] : slidesThatFit;
    }, []);
  }
  function getSlideBounds(offset) {
    return snaps.map((snap, index) => ({
      start: snap - slideSizes[index] + roundingSafety + offset,
      end: snap + viewSize - roundingSafety + offset
    }));
  }
  function getLoopPoints(indexes, offset, isEndEdge) {
    const slideBounds = getSlideBounds(offset);
    return indexes.map(index => {
      const initial = isEndEdge ? 0 : -contentSize;
      const altered = isEndEdge ? contentSize : 0;
      const boundEdge = isEndEdge ? 'end' : 'start';
      const loopPoint = slideBounds[index][boundEdge];
      return {
        index,
        loopPoint,
        slideLocation: NumberStore(-1),
        translate: slideTranslates[index],
        target: () => location.get() > loopPoint ? initial : altered
      };
    });
  }
  function startPoints() {
    const gap = scrollSnaps[0];
    const indexes = getSlidesThatFitGap(descItems, gap);
    return getLoopPoints(indexes, contentSize, false);
  }
  function endPoints() {
    const gap = viewSize - scrollSnaps[0] - 1;
    const indexes = getSlidesThatFitGap(ascItems, gap);
    return getLoopPoints(indexes, -contentSize, true);
  }
  function canLoop() {
    return loopPoints.every(({
      index
    }) => {
      const otherIndexes = ascItems.filter(i => i !== index);
      return getRemainingGapAfterSlides(otherIndexes, viewSize) <= 0.1;
    });
  }
  function loop() {
    loopPoints.forEach(loopPoint => {
      const {
        target,
        translate,
        slideLocation
      } = loopPoint;
      const shiftLocation = target();
      if (shiftLocation === slideLocation.get()) return;
      translate.to(shiftLocation);
      slideLocation.set(shiftLocation);
    });
  }
  const self = {
    canLoop,
    loop,
    loopPoints
  };
  return self;
}

function SlidesHandler(active, container, eventHandler) {
  let mutationObserver;
  let destroyed = false;
  function init(ownerWindow) {
    if (!active) return;
    mutationObserver = new ownerWindow.MutationObserver(onSlidesChange);
    mutationObserver.observe(container, {
      childList: true
    });
  }
  function destroy() {
    if (mutationObserver) mutationObserver.disconnect();
    destroyed = true;
  }
  function onSlidesChange(mutations) {
    const event = eventHandler.createEvent('slideschanged', mutations);
    const preventDefault = !event.emit();
    if (preventDefault) return;
    for (const mutation of mutations) {
      if (destroyed) return;
      if (mutation.type === 'childList') {
        event.api.reInit();
        break;
      }
    }
  }
  const self = {
    init,
    destroy
  };
  return self;
}

function SlidesInView(container, slides, eventHandler, threshold, rootMargin) {
  const slidesInView = new Set();
  let intersectionObserver;
  let destroyed = false;
  function init(ownerWindow) {
    intersectionObserver = new ownerWindow.IntersectionObserver(onIntersection, {
      root: container.parentElement,
      threshold,
      rootMargin
    });
    slides.forEach(slide => intersectionObserver.observe(slide));
  }
  function destroy() {
    if (intersectionObserver) intersectionObserver.disconnect();
    destroyed = true;
  }
  function onIntersection(entries) {
    const slidesEnterView = [];
    const slidesLeftView = [];
    for (const entry of entries) {
      if (destroyed) return;
      const index = slides.indexOf(entry.target);
      if (entry.isIntersecting) {
        slidesInView.add(index);
        slidesEnterView.push(index);
      } else {
        slidesInView.delete(index);
        slidesLeftView.push(index);
      }
    }
    const event = eventHandler.createEvent('slidesinview', {
      slidesInView: get(),
      slidesLeftView,
      slidesEnterView
    });
    event.emit();
  }
  function get() {
    return [...slidesInView];
  }
  const self = {
    init,
    destroy,
    get
  };
  return self;
}

function SlideSizes(axis, containerRect, slideRects, slides, readEdgeGap, nodeHandler) {
  const {
    ownerWindow
  } = nodeHandler;
  const {
    getSize,
    startEdge,
    endEdge
  } = axis;
  const withEdgeGap = slideRects[0] && readEdgeGap && ownerWindow;
  const startGap = getStartGap();
  const endGap = getEndGap();
  const slideSizes = slideRects.map(getSize);
  const slideSizesWithGaps = getSlideSizesWithGaps();
  function getStartGap() {
    if (!withEdgeGap) return 0;
    const slideRect = slideRects[0];
    return mathAbs(containerRect[startEdge] - slideRect[startEdge]);
  }
  function getEndGap() {
    if (!withEdgeGap) return 0;
    const style = ownerWindow.getComputedStyle(arrayLast(slides));
    return parseFloat(style.getPropertyValue(`margin-${endEdge}`));
  }
  function getSlideSizesWithGaps() {
    return slideRects.map((rect, index, rects) => {
      const isFirst = !index;
      const isLast = arrayIsLastIndex(rects, index);
      if (isFirst) return slideSizes[index] + startGap;
      if (isLast) return slideSizes[index] + endGap;
      return rects[index + 1][startEdge] - rect[startEdge];
    }).map(mathAbs);
  }
  const self = {
    slideSizes,
    slideSizesWithGaps,
    startGap,
    endGap
  };
  return self;
}

function SlidesToScroll(axis, viewSize, slidesToScroll, loop, containerRect, slideRects, startGap, endGap, pixelTolerance) {
  const {
    startEdge,
    endEdge,
    direction
  } = axis;
  const groupByNumber = isNumber(slidesToScroll);
  function byNumber(array, groupSize) {
    return arrayKeys(array).filter(i => i % groupSize === 0).map(i => array.slice(i, i + groupSize));
  }
  function bySize(array) {
    if (!array.length) return [];
    return arrayKeys(array).reduce((groups, rectB, index) => {
      const rectA = arrayLast(groups) || 0;
      const isFirst = rectA === 0;
      const isLast = rectB === arrayLastIndex(array);
      const edgeA = containerRect[startEdge] - slideRects[rectA][startEdge];
      const edgeB = containerRect[startEdge] - slideRects[rectB][endEdge];
      const gapA = !loop && isFirst ? direction(startGap) : 0;
      const gapB = !loop && isLast ? direction(endGap) : 0;
      const chunkSize = mathAbs(edgeB - gapB - (edgeA + gapA));
      if (index && chunkSize > viewSize + pixelTolerance) groups.push(rectB);
      if (isLast) groups.push(array.length);
      return groups;
    }, []).map((currentSize, index, groups) => {
      const previousSize = Math.max(groups[index - 1] || 0);
      return array.slice(previousSize, currentSize);
    });
  }
  function groupSlides(array) {
    return groupByNumber ? byNumber(array, slidesToScroll) : bySize(array);
  }
  const self = {
    groupSlides
  };
  return self;
}

function Translate(axis, node) {
  const getTranslate = axis.scroll === 'x' ? x : y;
  const nodeStyle = node.style;
  let previousTarget;
  let disabled = false;
  function x(input) {
    return `translate3d(${input}px,0px,0px)`;
  }
  function y(input) {
    return `translate3d(0px,${input}px,0px)`;
  }
  function to(input) {
    if (disabled) return;
    const newTarget = roundToTwoDecimals(axis.direction(input));
    if (newTarget === previousTarget) return;
    nodeStyle.transform = getTranslate(newTarget);
    previousTarget = newTarget;
  }
  function toggleActive(active) {
    disabled = !active;
  }
  function clear() {
    nodeStyle.transform = '';
    if (!node.getAttribute('style')) node.removeAttribute('style');
  }
  const self = {
    clear,
    to: mapStoreToNumber(to),
    toggleActive
  };
  return self;
}

function Engine(root, container, slides, options, nodeHandler, eventHandler, rects, isSsr) {
  // Options
  const {
    align,
    axis: scrollAxis,
    direction,
    startSnap,
    loop,
    duration,
    dragFree,
    dragThreshold,
    inViewThreshold,
    inViewMargin,
    slidesToScroll: groupSlides,
    skipSnaps,
    containScroll,
    draggable,
    resize,
    slideChanges,
    focus
  } = options;
  // Measurements
  const pixelTolerance = isSsr ? 0 : 2;
  const axis = Axis(scrollAxis, direction);
  const {
    containerRect,
    slideRects
  } = rects;
  const viewSize = axis.getSize(containerRect);
  const percentOfView = PercentOfView(viewSize);
  const alignment = Alignment(align, viewSize);
  const containSnaps = !loop && !!containScroll;
  const readEdgeGap = loop || !!containScroll;
  const {
    slideSizes,
    slideSizesWithGaps,
    startGap,
    endGap
  } = SlideSizes(axis, containerRect, slideRects, slides, readEdgeGap, nodeHandler);
  const slidesToScroll = SlidesToScroll(axis, viewSize, groupSlides, loop, containerRect, slideRects, startGap, endGap, pixelTolerance);
  const {
    snaps,
    snapsAligned
  } = ScrollSnaps(axis, alignment, containerRect, slideRects, slidesToScroll);
  const contentSize = -arrayLast(snaps) + arrayLast(slideSizesWithGaps);
  const {
    snapsContained,
    scrollContainLimit
  } = ScrollContain(viewSize, contentSize, snapsAligned, containScroll, pixelTolerance);
  const scrollSnaps = containSnaps ? snapsContained : snapsAligned;
  const {
    limit
  } = ScrollLimit(contentSize, scrollSnaps, loop);
  // Indexes
  const indexCurrent = Counter(arrayLastIndex(scrollSnaps), startSnap, loop);
  const indexPrevious = indexCurrent.clone();
  const slideIndexes = arrayKeys(slides);
  // Animation
  const scrollAnimator = ScrollAnimator();
  const animation = Animations(() => scrollAnimator.update(engine), alpha => scrollAnimator.render(engine, alpha));
  // Shared
  const friction = 0.68;
  const startLocation = scrollSnaps[indexCurrent.get()];
  const location = NumberStore(startLocation);
  const previousLocation = NumberStore(startLocation);
  const offsetLocation = NumberStore(startLocation);
  const target = NumberStore(startLocation);
  const translate = Translate(axis, container);
  const slideTranslates = slides.map(slide => Translate(axis, slide));
  const scrollProgress = ScrollProgress(limit);
  const scrollBody = ScrollBody(location, offsetLocation, previousLocation, target, duration, friction);
  const scrollSnapList = ScrollSnapList(containSnaps, containScroll, scrollSnaps, scrollContainLimit, slidesToScroll, slideIndexes, scrollProgress);
  const slideLooper = SlideLooper(viewSize, contentSize, slideSizes, slideSizesWithGaps, snaps, scrollSnaps, offsetLocation, slideTranslates);
  const scrollTarget = ScrollTarget(loop, scrollSnaps, contentSize, limit, target);
  const scrollTo = ScrollTo(animation, indexCurrent, indexPrevious, scrollBody, scrollTarget, target, eventHandler);
  const eventStore = EventStore();
  const slidesInView = SlidesInView(container, slides, eventHandler, inViewThreshold, inViewMargin);
  const slideFocus = SlideFocus(axis, focus, root, slides, scrollSnapList, scrollTo, scrollBody, eventStore, eventHandler);
  // Engine
  const engine = {
    eventHandler,
    containerRect,
    contentSize,
    slideRects,
    nodeHandler,
    animation,
    slideSizes,
    isSsr,
    axis,
    dragHandler: DragHandler(draggable, axis, root, target, DragTracker(axis), location, animation, scrollTo, scrollBody, scrollTarget, indexCurrent, eventHandler, percentOfView, dragFree, dragThreshold, skipSnaps, friction),
    eventStore,
    percentOfView,
    indexCurrent,
    indexPrevious,
    limit,
    location,
    offsetLocation,
    previousLocation,
    options,
    resizeHandler: ResizeHandler(resize, container, eventHandler, slides, axis, nodeHandler),
    scrollBody,
    scrollBounds: ScrollBounds(limit, offsetLocation, target, scrollBody, percentOfView),
    scrollLooper: ScrollLooper(contentSize, limit, offsetLocation, [location, offsetLocation, previousLocation, target]),
    scrollProgress,
    scrollSnaps,
    scrollTarget,
    scrollTo,
    slideLooper,
    slideFocus,
    slidesHandler: SlidesHandler(slideChanges, container, eventHandler),
    slidesInView,
    slideIndexes,
    slidesToScroll,
    slideTranslates,
    scrollSnapList,
    translate,
    target
  };
  return engine;
}

function EventHandler() {
  let eventStore = {};
  let api;
  function init(emblaApi) {
    api = emblaApi;
  }
  function getStore(type) {
    return eventStore[type] || [];
  }
  function setStore(type, update) {
    eventStore = Object.assign(Object.assign({}, eventStore), {
      [type]: update(getStore(type))
    });
    return self;
  }
  function createEventModel(type, detail) {
    return {
      api,
      type,
      detail
    };
  }
  function createEvent(type, detail) {
    const event = {
      api,
      emit: () => emit(type, detail)
    };
    return event;
  }
  function emit(type, detail) {
    const event = createEventModel(type, detail);
    return getStore(type).every(handler => handler(api, event) !== false);
  }
  function on(type, callback) {
    setStore(type, handlers => {
      return handlers.includes(callback) ? handlers : [...handlers, callback];
    });
    return self;
  }
  function off(type, callback) {
    setStore(type, handlers => {
      return handlers.filter(handler => handler !== callback);
    });
    return self;
  }
  function clear() {
    eventStore = {};
  }
  const self = {
    init,
    clear,
    createEvent,
    on,
    off
  };
  return self;
}

const defaultOptions = {
  align: 'center',
  axis: 'x',
  container: null,
  slides: null,
  containScroll: 'trimSnaps',
  direction: 'ltr',
  slidesToScroll: 1,
  inViewThreshold: 0,
  inViewMargin: '0px',
  breakpoints: {},
  dragFree: false,
  dragThreshold: 10,
  loop: false,
  skipSnaps: false,
  duration: 25,
  startSnap: 0,
  active: true,
  draggable: true,
  resize: true,
  focus: true,
  slideChanges: true
};

function NodeHandler(root) {
  const ownerDocument = root ? root.ownerDocument : null;
  const ownerWindow = ownerDocument ? ownerDocument.defaultView : null;
  let rects;
  function getRect(node) {
    const {
      offsetTop: top,
      offsetLeft: left,
      offsetWidth,
      offsetHeight
    } = node;
    const offset = {
      top,
      right: left + offsetWidth,
      bottom: top + offsetHeight,
      left,
      width: offsetWidth,
      height: offsetHeight
    };
    return offset;
  }
  function getRects(container, slides, fromCache) {
    if (fromCache && rects) return rects;
    const containerStyle = root ? container.style : {
      transform: ''
    };
    const previousTransform = containerStyle.transform;
    containerStyle.transform = 'none';
    const containerRect = getRect(container);
    const slideRects = slides.map(getRect);
    containerStyle.transform = previousTransform;
    rects = {
      containerRect,
      slideRects
    };
    return rects;
  }
  function getNodes(options) {
    if (!root) {
      return {
        root: {},
        container: {},
        slides: []
      };
    }
    const {
      container: userContainer,
      slides: userSlides
    } = options;
    const containerNode = isString(userContainer) ? root.querySelector(userContainer) : userContainer;
    const container = containerNode || root.children[0];
    const slideNodes = isString(userSlides) ? container.querySelectorAll(userSlides) : userSlides;
    const slides = Array.from(slideNodes || container.children);
    return {
      root,
      container,
      slides
    };
  }
  const self = {
    ownerDocument,
    ownerWindow,
    getNodes,
    getRect,
    getRects
  };
  return self;
}

function OptionsHandler() {
  let windowInstance;
  function init(ownerWindow) {
    if (ownerWindow) windowInstance = ownerWindow;
  }
  function mergeOptions(optionsA, optionsB) {
    return objectsMergeDeep(optionsA, optionsB || {});
  }
  function optionsAtMedia(options) {
    if (!windowInstance) return options;
    const optionsAtMedia = options.breakpoints || {};
    const matchedMediaOptions = objectKeys(optionsAtMedia).filter(media => windowInstance.matchMedia(media).matches).map(media => optionsAtMedia[media]).reduce((mediaOptions, mediaOption) => mergeOptions(mediaOptions, mediaOption), {});
    return mergeOptions(options, matchedMediaOptions);
  }
  function optionsMediaQueries(optionsList) {
    if (!windowInstance) return [];
    return optionsList.map(options => objectKeys(options.breakpoints || {})).reduce((mediaQueries, mediaQuery) => mediaQueries.concat(mediaQuery), []).map(windowInstance.matchMedia);
  }
  const self = {
    init,
    mergeOptions,
    optionsAtMedia,
    optionsMediaQueries
  };
  return self;
}

function PluginsHandler(optionsHandler) {
  let activePlugins = [];
  function init(emblaApi, plugins) {
    activePlugins = plugins;
    return plugins.reduce((pluginList, plugin) => {
      plugin.init(emblaApi, optionsHandler);
      return Object.assign(Object.assign({}, pluginList), {
        [plugin.name]: plugin
      });
    }, {});
  }
  function destroy() {
    activePlugins = activePlugins.filter(plugin => plugin.destroy());
  }
  const self = {
    init,
    destroy
  };
  return self;
}

function EmblaCarousel(userRoot, userOptions, userPlugins) {
  const isSsr = !userRoot;
  const optionsHandler = OptionsHandler();
  const pluginsHandler = PluginsHandler(optionsHandler);
  const mediaHandlers = EventStore();
  const eventHandler = EventHandler();
  const {
    mergeOptions,
    optionsAtMedia,
    optionsMediaQueries
  } = optionsHandler;
  const {
    on,
    off,
    createEvent
  } = eventHandler;
  const reInit = reActivate;
  let destroyed = false;
  let engine;
  let nodeHandler;
  let optionsBase = mergeOptions(defaultOptions, EmblaCarousel.globalOptions);
  let options = mergeOptions(optionsBase);
  let pluginList = [];
  let pluginApis = {};
  let root;
  let container;
  let slides;
  function cloneEngine(userOptions) {
    const engineOptions = mergeOptions(options, userOptions);
    return createEngine(engineOptions, container, slides, true);
  }
  function createEngine(options, container, slides, useCachedRects) {
    const rects = nodeHandler.getRects(container, slides, useCachedRects);
    const engine = Engine(root, container, slides, options, nodeHandler, eventHandler, rects, isSsr);
    if (options.loop && !engine.slideLooper.canLoop()) {
      return cloneEngine({
        loop: false
      });
    }
    return engine;
  }
  function activate(withOptions, withPlugins) {
    if (destroyed) return;
    nodeHandler = NodeHandler(userRoot);
    const {
      ownerWindow
    } = nodeHandler;
    optionsHandler.init(ownerWindow);
    optionsBase = mergeOptions(optionsBase, withOptions);
    options = optionsAtMedia(optionsBase);
    pluginList = withPlugins || pluginList;
    let engineOptions = options;
    let nodes = nodeHandler.getNodes(options);
    const ssrHandler = getSsrHandler(pluginList);
    if (isSsr && ssrHandler) {
      ssrHandler.setup(createEngine, mergeOptions, optionsBase);
      engineOptions = mergeOptions(engineOptions, {
        direction: 'ltr'
      });
      nodes = ssrHandler.getNodes();
    }
    root = nodes.root;
    container = nodes.container;
    slides = nodes.slides;
    engine = createEngine(engineOptions, container, slides);
    optionsMediaQueries([optionsBase, ...pluginList.map(({
      options
    }) => options)]).forEach(query => mediaHandlers.add(query, 'change', reActivate));
    if (!options.active) return;
    if (!isSsr && ownerWindow) {
      engine.translate.to(engine.location);
      if (engine.options.loop) engine.slideLooper.loop();
      engine.animation.init(ownerWindow);
      engine.resizeHandler.init(ownerWindow);
      engine.slidesInView.init(ownerWindow);
      engine.slidesHandler.init(ownerWindow);
      engine.slideFocus.init(ownerWindow);
      engine.eventHandler.init(self);
      if (container.offsetParent && slides.length) {
        engine.dragHandler.init(ownerWindow);
      }
    }
    pluginApis = pluginsHandler.init(self, pluginList);
  }
  function reActivate(withOptions, withPlugins) {
    const event = eventHandler.createEvent('reinit', null);
    const startSnap = selectedSnap();
    deActivate();
    activate(mergeOptions({
      startSnap
    }, withOptions), withPlugins);
    event.emit();
  }
  function deActivate() {
    engine.dragHandler.destroy();
    engine.resizeHandler.destroy();
    engine.slidesHandler.destroy();
    engine.slidesInView.destroy();
    engine.animation.destroy();
    pluginsHandler.destroy();
    engine.eventStore.clear();
    mediaHandlers.clear();
    engine.translate.clear();
    engine.slideTranslates.forEach(translate => translate.clear());
  }
  function destroy() {
    if (destroyed) return;
    if (isSsr) return;
    const event = eventHandler.createEvent('destroy', null);
    destroyed = true;
    mediaHandlers.clear();
    deActivate();
    event.emit();
    eventHandler.clear();
  }
  function goTo(index, instant, direction) {
    if (destroyed) return;
    if (isSsr) return;
    if (!options.active) return;
    engine.scrollBody.useBaseFriction().useDuration(instant === true ? 0 : options.duration);
    engine.scrollTo.index(index, direction);
  }
  function goToNext(instant) {
    goTo(snapIndex(1), instant, -1);
  }
  function goToPrev(instant) {
    goTo(snapIndex(-1), instant, 1);
  }
  function canGoToNext() {
    return snapIndex(1) !== selectedSnap();
  }
  function canGoToPrev() {
    return snapIndex(-1) !== selectedSnap();
  }
  function scrollProgress() {
    return engine.scrollProgress.get(engine.offsetLocation);
  }
  function snapIndex(offset) {
    return engine.indexCurrent.add(offset).get();
  }
  function snapList() {
    return engine.scrollSnapList.progressBySnap;
  }
  function selectedSnap() {
    return snapIndex(0);
  }
  function previousSnap() {
    return engine.indexPrevious.get();
  }
  function slidesInView() {
    return engine.slidesInView.get();
  }
  function plugins() {
    return pluginApis;
  }
  function internalEngine() {
    return engine;
  }
  function rootNode() {
    return root;
  }
  function containerNode() {
    return container;
  }
  function slideNodes() {
    return slides;
  }
  const self = {
    canGoToNext,
    canGoToPrev,
    cloneEngine,
    containerNode,
    createEvent,
    internalEngine,
    destroy,
    on,
    off,
    plugins,
    previousSnap,
    reInit,
    rootNode,
    goToNext,
    goToPrev,
    scrollProgress,
    goTo,
    selectedSnap,
    slideNodes,
    slidesInView,
    snapIndex,
    snapList
  };
  activate(userOptions || {}, userPlugins || []);
  return self;
}
EmblaCarousel.globalOptions = undefined;

module.exports = EmblaCarousel;
//# sourceMappingURL=embla-carousel.cjs.js.map
