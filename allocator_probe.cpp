#include <cstring>
#include <iostream>

#include "rapidjson/document.h"
#include "rapidjson/pointer.h"
#include "rapidjson/schema.h"
#include "rapidjson/stringbuffer.h"
#include "rapidjson/writer.h"

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "Expected a test case name\n";
        return 2;
    }

    const char* schemaText = nullptr;
    const char* instanceText = nullptr;
    bool expectedValid = false;
    const char* name = argv[1];

    if (std::strcmp(name, "root-invalid") == 0) {
        schemaText = R"({"type":"object","dependencies":{"credit_card":["billing_address"]}})";
        instanceText = R"({"credit_card":123})";
    } else if (std::strcmp(name, "nested-invalid") == 0) {
        schemaText = R"({"type":"object","properties":{"order":{"type":"object","dependencies":{"credit_card":["billing_address"]}}}})";
        instanceText = R"({"order":{"credit_card":123}})";
    } else if (std::strcmp(name, "valid") == 0) {
        schemaText = R"({"type":"object","dependencies":{"credit_card":["billing_address"]}})";
        instanceText = R"({"credit_card":123,"billing_address":"present"})";
        expectedValid = true;
    } else if (std::strcmp(name, "trigger-absent") == 0) {
        schemaText = R"({"type":"object","dependencies":{"credit_card":["billing_address"]}})";
        instanceText = R"({})";
        expectedValid = true;
    } else if (std::strcmp(name, "escaped-invalid") == 0) {
        schemaText = R"({"type":"object","dependencies":{"a/b~key":["must~have/x"]}})";
        instanceText = R"({"a/b~key":1})";
    } else if (std::strcmp(name, "schema-dependency-invalid") == 0) {
        schemaText = R"({"type":"object","dependencies":{"credit_card":{"required":["billing_address"]}}})";
        instanceText = R"({"credit_card":123})";
    } else if (std::strcmp(name, "ordinary-required-invalid") == 0) {
        schemaText = R"({"type":"object","required":["billing_address"]})";
        instanceText = R"({})";
    } else if (std::strcmp(name, "empty-pointer") == 0) {
        rapidjson::Pointer pointer;
        std::cout << "Requesting the default pointer's allocator reference\n";
        auto* allocator = &pointer.GetAllocator();
        std::cout << "Allocator address: " << static_cast<void*>(allocator) << "\n";
        return 0;
    } else {
        std::cerr << "Unknown test case: " << name << "\n";
        return 2;
    }

    rapidjson::Document schemaJson;
    rapidjson::Document instance;
    schemaJson.Parse(schemaText);
    instance.Parse(instanceText);
    if (schemaJson.HasParseError() || instance.HasParseError()) {
        std::cerr << "Malformed fixture JSON\n";
        return 2;
    }

    rapidjson::SchemaDocument schema(schemaJson);
    rapidjson::SchemaValidator validator(schema);
    const bool accepted = instance.Accept(validator);
    const bool valid = validator.IsValid();
    rapidjson::StringBuffer buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
    validator.GetError().Accept(writer);
    std::cout << "{\"case\":\"" << name << "\",\"accepted\":"
              << (accepted ? "true" : "false") << ",\"valid\":"
              << (valid ? "true" : "false") << ",\"error\":"
              << buffer.GetString() << "}\n";

    if (accepted != expectedValid || valid != expectedValid) {
        std::cerr << "Validation result disagreed with the fixture\n";
        return 3;
    }
    return 0;
}
