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
        tag_type: Tag,
        tag_value: String
    }],
    description: String
})

const Organization = scholarDB.model('Organization', orgSchema);
module.exports = Organization;
*/