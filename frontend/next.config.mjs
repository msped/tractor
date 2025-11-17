const nextConfig = {
  ...(process.env.CYPRESS_TEST
    ? {}
    : {
        turbopack: {},
      }),
  webpack(config, { dev, isServer }) {
    if (process.env.CYPRESS_TEST) {
      config.module.rules.push({
        test: /\.(js|ts|jsx|tsx)$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
          options: {
            presets: ["next/babel"],
            plugins: ["istanbul"],
          },
        },
      });
    }
    return config;
  },
};

export default nextConfig;