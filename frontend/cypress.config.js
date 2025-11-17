const { defineConfig } = require("cypress");

module.exports = defineConfig({
  viewportWidth: 1000,
  viewportHeight: 660,
  env: {
    codeCoverage: {
      exclude: ['cypress/**/*.*'],
    },
  },
  experimentalSingleTabRunMode: true,
  component: {
    devServer: {
      framework: "next",
      bundler: "webpack",
    },
    setupNodeEvents(on, config) {
      require('@cypress/code-coverage/task')(on, config)
      // include any other plugin code...

      // It's IMPORTANT to return the config object
      // with any changed environment variables
      return config
    },
  },
});
