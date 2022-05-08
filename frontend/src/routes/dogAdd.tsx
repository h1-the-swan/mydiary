import React from "react";
import { Form, Typography, Input, Button } from "antd";

//TODO
const DogAdd = () => {
  const [form] = Form.useForm();

  const onSubmit = (values: any) => {
    console.log(values);
  };

  return (
    <Form form={form} onFinish={onSubmit}>
      <Form.Item name="name" label="Name">
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit">
          Submit
        </Button>
      </Form.Item>
    </Form>
  );
};

export default DogAdd;
