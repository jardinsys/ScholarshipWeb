const mongoose = require("mongoose");

const MONGO_URI = process.env.MONGO_URI || 'mongodb://crawler-mongo:27017/scholarshipdb' // Could use an environment variable but will be using a local host to develope the prototype

const connect = async () => {
    await mongoose.connect(MONGO_URI);
    console.log("[db] Connected to MongoDB:", MONGO_URI);
};

module.exports = {mongoose, connect};