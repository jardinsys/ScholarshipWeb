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
        tag_type: { type: mongoose.Schema.Types.ObjectId, ref: 'Tag', required: true },
        tag_value: { type: mongoose.Schema.Types.Mixed, required: true }
    }],
    bio: String,
    join_date: { type: Date, default: Date.now },
    saved_scholarships: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Scholarship' }]
})

const User = scholarDB.model('User', userSchema);
module.exports = User;