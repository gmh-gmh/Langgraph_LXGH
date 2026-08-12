/**
 * main.js — Vue 3 应用入口
 *
 * 【面试要点】
 * 1. 为什么 Vite 的入口是 main.js 而不是 index.html 直接引用组件？
 *    → Vite 以 main.js 为依赖图入口，从这开始解析 import 树，
 *      实现按需编译（只会编译被 import 到的文件）
 *
 * 2. app.use(naive) 做了什么？
 *    → naive-ui 是一个 Vue 插件（plugin），app.use() 会调用其 install 方法，
 *      全局注册所有组件和指令，并提供主题配置能力
 *    → 缺点：全局注册可能导致未使用的组件也被打包
 *    → 替代方案：按需引入（手动 import 每个组件），但开发效率低
 */

import { createApp } from 'vue'   // Vue 3 的 createApp API（Vue 2 是 new Vue()）
import App from './App.vue'        // 根组件
import './style.css'               // 全局样式（Normalize + 滚动条美化）
import naive from 'naive-ui'       // Naive UI 组件库（暗黑主题 UI）

const app = createApp(App)         // 创建应用实例

// 注册 Naive UI 插件 —— 这会让所有 naive-ui 组件在全局可用
// 面试点：app.use() 与全局注册 vs 按需引入的权衡
app.use(naive)

// 挂载到 index.html 中的 #app 元素上
// 面试点：createApp 替代了 Vue 2 的 new Vue({el: '#app'})
// 好处：一个页面可以有多个 Vue 应用实例（微前端场景）
app.mount('#app')
