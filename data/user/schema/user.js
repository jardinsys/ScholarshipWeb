const mongoose = require("mongoose");
const scholarDB = require("../../database"); //fix location later
const Snowflake = require('snowflake-id').default;
const snowflake = new Snowflake({
    mid: 1,  // Machine ID
    offset: 0
});

const userSchema = new mongoose.Schema({
    id: { type: String, default: () => snowflake.generate(), unique: true},
    displayname: String, 
    username: String,
    tags: [{
        tag_type: Tag,
        tag_value: String
    }],
    bio: String,
    join_date: Date
})

const User = scholarDBDB.model('User', userSchema);
module.exports = User;