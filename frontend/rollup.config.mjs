import path from 'node:path'
import { fileURLToPath } from 'node:url'
import resolve from '@rollup/plugin-node-resolve'
import commonjs from '@rollup/plugin-commonjs'
import babel from '@rollup/plugin-babel'
import replace from '@rollup/plugin-replace'
import json from '@rollup/plugin-json'
import postcss from 'rollup-plugin-postcss'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default {
  input: path.join(__dirname, 'src/main.jsx'),
  output: {
    file: path.join(__dirname, 'dist/assets/app.js'),
    format: 'es',
    sourcemap: false,
  },
  plugins: [
    replace({
      preventAssignment: true,
      'process.env.NODE_ENV': JSON.stringify('production'),
    }),
    postcss({
      extract: 'app.css',
      minimize: true,
      config: { path: path.join(__dirname, 'postcss.config.js') },
    }),
    babel({
      babelHelpers: 'bundled',
      babelrc: false,
      configFile: false,
      extensions: ['.js', '.jsx'],
      exclude: 'node_modules/**',
      presets: [
        ['@babel/preset-react', { runtime: 'automatic', development: false }],
        ['@babel/preset-env', { targets: 'defaults', modules: false }],
      ],
    }),
    resolve({
      browser: true,
      preferBuiltins: false,
      mainFields: ['browser', 'module', 'main'],
      extensions: ['.js', '.jsx'],
    }),
    commonjs(),
    json(),
  ],
}
