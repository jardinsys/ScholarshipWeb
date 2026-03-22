const mongoose = require("mongoose");

const MONGO_URI = process.env.MONGO_URI || "mongodb://localhost:27017/scholarshipdb";

mongoose.connect(MONGO_URI).then(() => {
    console.log("[db] Connected to MongoDB:", MONGO_URI);
}).catch((err) => {
    console.error("[db] MongoDB connection error:", err);
    process.exit(1);
});

module.exports = mongoose;