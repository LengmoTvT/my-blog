/**
 * 冷漠博客 - 文章内联图片自动增强过滤器
 * 不用 cheerio，零依赖。直接正则处理 <img>：
 * 1. 包裹 <a data-fancybox="gallery"> 支持点击放大（修复 "cannot be loaded"）
 * 2. 加 class=article-image（CSS 居中+自适应+圆角）
 * 3. src 走 urlFor 解决 post_asset_folder 相对路径
 */
'use strict';

hexo.extend.filter.register('after_post_render', (data) => {
  if (!data.content) return data;
  if (data.layout !== 'post' && data.layout !== 'page') return data;

  const urlFor = require('hexo-util').url_for.bind(hexo);

  // 用 post._permalink 或 post.path 推断 asset 根目录
  // 让 "xxx.png" 解析成 "/2026/xx/xx/文章标题/xxx.png"
  let assetPrefix = '';
  if (data.path) {
    const p = data.path.replace(/\\/g, '/');
    const m = p.match(/^(.*\/)([^\/]*)(?:\.html)?$/i);
    if (m && m[1]) assetPrefix = '/' + m[1].replace(/^\/+/, '');
  } else if (data.asset_dir) {
    // asset_dir 是本地绝对路径，截取 source/_posts/ 后面的部分
    const rel = require('path').relative(hexo.source_dir, data.asset_dir).replace(/\\/g, '/');
    if (rel && !rel.startsWith('..')) assetPrefix = '/' + rel.replace(/^\/+/, '') + '/';
  }

  data.content = data.content.replace(
    /<img([^>]*?)(?:\/>|>)/gi,
    (match, attrs) => {
      // 跳过行内小图 inline-img
      if (/\bclass\s*=\s*["'][^"']*inline-img[^"']*["']/i.test(attrs)) {
        return match;
      }

      // 提取 src
      const srcMatch = attrs.match(/\bsrc\s*=\s*["']([^"']+)["']/i);
      let src = srcMatch ? srcMatch[1] : '';

      // 提取 alt
      const altMatch = attrs.match(/\balt\s*=\s*["']([^"']*)["']/i);
      const alt = altMatch ? altMatch[1] : '';

      // 处理本地路径（纯文件名形式 -> 解析成文章 asset 目录下）
      if (src && !/^https?:\/\//i.test(src) && !src.startsWith('//')) {
        let fixed = src;
        const srcForTest = src.startsWith('/') ? src.slice(1) : src;
        if (!/[\/\\]/.test(srcForTest) && assetPrefix) {
          fixed = assetPrefix + srcForTest;
        }
        try { fixed = urlFor(fixed); } catch (e) {}
        src = fixed;
      }

      // 去重 src，去掉已有 class（后面统一加）
      let newAttrs = attrs.replace(/\bsrc\s*=\s*["'][^"']*["']/i, '');
      newAttrs = newAttrs.replace(/\bclass\s*=\s*["']([^"']*)["']/i, (m, cls) => {
        return 'class="' + cls.trim() + ' article-image"';
      });
      if (!/\bclass\s*=/.test(newAttrs)) {
        newAttrs += ' class="article-image"';
      }
      newAttrs += ' src="' + src + '"';
      if (!/\bloading\s*=/.test(newAttrs)) {
        newAttrs += ' loading="lazy"';
      }
      const altEscaped = alt.replace(/"/g, '&quot;');
      if (alt && !/\btitle\s*=/.test(newAttrs)) {
        newAttrs += ' title="' + altEscaped + '"';
      }

      const caption = alt ? ' data-caption="' + altEscaped + '"' : '';
      return '<a href="' + src + '" data-fancybox="gallery" class="article-image-link"' + caption + '>'
           + '<img' + newAttrs + ' />'
           + '</a>';
    }
  );

  return data;
}, 10);
