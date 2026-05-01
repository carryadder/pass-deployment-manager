var config = {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"Space Grotesk"', "ui-sans-serif", "system-ui", "sans-serif"],
                serif: ['"Source Serif 4"', "ui-serif", "Georgia", "serif"],
            },
            colors: {
                ink: "#10131a",
                mist: "#f6f4ef",
                coral: "#ef7d57",
                cyan: "#54d2d2",
                moss: "#9bc53d",
                slate: "#293241",
            },
            boxShadow: {
                panel: "0 24px 80px rgba(16, 19, 26, 0.14)",
            },
            backgroundImage: {
                grain: "radial-gradient(circle at 20% 20%, rgba(239,125,87,0.16), transparent 30%), radial-gradient(circle at 80% 0%, rgba(84,210,210,0.16), transparent 28%), radial-gradient(circle at 50% 100%, rgba(155,197,61,0.16), transparent 30%)",
            },
        },
    },
    plugins: [],
};
export default config;
