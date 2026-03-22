// Uncomment if this is a needed schema

/*const mongoose = require("mongoose");
const scholarDB = require("../../database"); //fix location later
const Snowflake = require('snowflake-id').default;
const snowflake = new Snowflake({
    mid: 1,  // Machine ID
    offset: 0
});

const orgSchema = new mongoose.Schema({
    id: { type: String, default: () => snowflake.generate(), unique: true},
    name: String, 
    provider: String, 
    url: String,
    tags: [{
        tag_type: { type: mongoose.Schema.Types.ObjectId, ref: 'Tag', required: true },
        tag_value: { type: mongoose.Schema.Types.Mixed, required: true }
    }],
    description: String
})

const Organization = scholarDB.model('Organization', orgSchema);
module.exports = Organization;
*/