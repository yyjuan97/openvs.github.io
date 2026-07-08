/* ===========================================================
   OpenVS 官网交互逻辑
   =========================================================== */
(function () {
  'use strict';

  /* ---------- 导航栏滚动变色 ---------- */
  var navbar = document.getElementById('navbar');
  window.addEventListener('scroll', function () {
    if (window.scrollY > 30) navbar.classList.add('scrolled');
    else navbar.classList.remove('scrolled');
  });

  /* ---------- 滚动淡入 ---------- */
  var revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('in'); });
  }

  /* ---------- 效果演示动画：文字逐字 + 节点浮现 ---------- */
  var DEMO_TEXT =
    '用户登录后，可选择手机验证或邮箱验证完成身份认证。' +
    '认证通过则进入主页，失败则返回重新登录。';

  var demoText = document.getElementById('demoText');
  var demoCaret = document.getElementById('demoCaret');
  var nodes = Array.prototype.slice.call(document.querySelectorAll('.d-node'));
  var edges = Array.prototype.slice.call(document.querySelectorAll('.d-edge'));

  // 节点按 i 排序，连线按 i 排序
  var sortedNodes = nodes.slice().sort(function (a, b) {
    return (+a.dataset.i) - (+b.dataset.i);
  });
  var sortedEdges = edges.slice().sort(function (a, b) {
    return (+a.dataset.i) - (+b.dataset.i);
  });

  function resetDemo() {
    demoText.textContent = '';
    sortedNodes.forEach(function (n) { n.classList.remove('show'); });
    sortedEdges.forEach(function (e) { e.classList.remove('show'); });
  }

  function runDemo() {
    resetDemo();

    // 1. 逐字打字
    var idx = 0;
    var typeTimer = setInterval(function () {
      demoText.textContent = DEMO_TEXT.slice(0, idx + 1);
      idx++;
      if (idx >= DEMO_TEXT.length) {
        clearInterval(typeTimer);
        // 2. 文字打完后，节点逐个浮现
        emergeShapes();
      }
    }, 55);
  }

  function emergeShapes() {
    // 节点逐个出现
    sortedNodes.forEach(function (n, i) {
      setTimeout(function () { n.classList.add('show'); }, i * 280);
    });

    // 连线在节点之后出现
    var nodesDelay = sortedNodes.length * 280 + 200;
    sortedEdges.forEach(function (e, i) {
      setTimeout(function () { e.classList.add('show'); }, nodesDelay + i * 130);
    });

    // 整段动画结束后，停留再循环
    var total = nodesDelay + sortedEdges.length * 130 + 2600;
    setTimeout(runDemo, total);
  }

  // 演示区进入视口时启动一次，之后自循环
  var demoSection = document.getElementById('demo');
  var demoStarted = false;
  if (demoSection && 'IntersectionObserver' in window) {
    var demoIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !demoStarted) {
          demoStarted = true;
          runDemo();
          demoIO.unobserve(e.target);
        }
      });
    }, { threshold: 0.3 });
    demoIO.observe(demoSection);
  } else {
    runDemo();
  }

  /* ---------- Hero 预览卡片：节点循环浮现 ---------- */
  var pvNodes = Array.prototype.slice.call(document.querySelectorAll('.pv-node'))
    .sort(function (a, b) { return (+a.dataset.i) - (+b.dataset.i); });
  var pvEdges = Array.prototype.slice.call(document.querySelectorAll('.pv-edge'))
    .sort(function (a, b) { return (+a.dataset.i) - (+b.dataset.i); });

  function runPreview() {
    pvNodes.forEach(function (n) { n.classList.remove('on'); });
    pvEdges.forEach(function (e) { e.classList.remove('on'); });

    pvNodes.forEach(function (n, i) {
      setTimeout(function () { n.classList.add('on'); }, i * 320);
    });
    var edgeStart = pvNodes.length * 320 + 150;
    pvEdges.forEach(function (e, i) {
      setTimeout(function () { e.classList.add('on'); }, edgeStart + i * 140);
    });

    var total = edgeStart + pvEdges.length * 140 + 2800;
    setTimeout(runPreview, total);
  }
  if (pvNodes.length) runPreview();

  /* ---------- 下载按钮提示（占位） ---------- */
  var dlBtn = document.getElementById('downloadBtn');
  if (dlBtn) {
    dlBtn.addEventListener('click', function (e) {
      // 占位：实际 exe 文件就绪前给出提示
      if (dlBtn.getAttribute('href') === '#') {
        e.preventDefault();
        var original = dlBtn.innerHTML;
        dlBtn.innerHTML = '下载链接即将就绪…';
        dlBtn.style.opacity = '0.85';
        setTimeout(function () {
          dlBtn.innerHTML = original;
          dlBtn.style.opacity = '';
        }, 2200);
      }
    });
  }
})();
