/**
 * vite.config.js — Vite 构建工具配置
 *
 * 面试点：为什么选 Vite 而不是 Webpack？
 * 1. 开发服务器：Vite 按需编译（esbuild），Webpack 全量打包（慢）
 * 2. HMR：Vite 热更新是 O(1) 级别，Webpack 随项目规模变慢
 * 3. 构建：Vite 用 Rollup（更成熟的 Tree-shaking），Webpack 用自己打包器
 * 4. 配置：Vite 零配置即可运行，Webpack 需要大量配置
 *
 * 什么情况选 Webpack？
 * - 需要兼容旧浏览器（Vite 目标现代浏览器）
 * - 项目深度使用了 Webpack loader 生态（如图片压缩、字体处理）
 * - 需要复杂的代码拆分策略
 */

import { defineConfig } from 'vite'    // Vite 配置类型提示
import vue from '@vitejs/plugin-vue'  // Vue 3 SFC 编译插件

export default defineConfig({
  // 插件 — Vue 3 单文件组件（.vue）编译支持
  plugins: [vue()],

  server: {
    // 开发服务器端口（默认 5173）
    port: 5173,

    /**
     * 代理配置 — 解决开发跨域问题
     *
     * 面试重点：
     * 【问题】前端在 5173 端口，后端在 8001 端口，浏览器同源策略会拦截
     * 【方案一：后端 CORS】后端设置 Access-Control-Allow-Origin: *
     *   → 后端已经做了（server.py 中 allow_origins=["*"]）
     *   → 但浏览器还是会发 OPTIONS 预检请求，增加延迟
     * 【方案二：Vite Proxy（本方案）】前端请求 /api/xxx → Vite 转发到 8001
     *   → 浏览器看到的是同域请求，没有跨域问题
     *   → 开发时不需要后端配 CORS
     * 【方案三：Nginx 反向代理】生产和开发都通过 Nginx 转发
     *   → 最接近生产环境，但需要额外配置
     *
     * 实际项目中通常是 方案二（开发） + 方案三（生产）的组合
     */
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',  // 后端 FastAPI 地址（IPv4）
        changeOrigin: true                 // 修改请求 Host 为目标地址
      }
    }
  }
})
