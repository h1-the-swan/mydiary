import { Alert, Button, Form, Input } from "antd";
import React from "react";
import {
  useGetGCalAuthUrl,
  useRefreshGCalToken,
  useCheckGCalAuth,
} from "../api";

export default function GCalRefreshToken() {
  const mutationCheckGCalAuth = useCheckGCalAuth();
  const { data: authUrl } = useGetGCalAuthUrl({
    query: { select: (d) => d.data },
  });
  const mutationGCalRefreshToken = useRefreshGCalToken();
  const [form] = Form.useForm();
  return (
    <React.Fragment>
      <Button
        type="primary"
        onClick={() => mutationCheckGCalAuth.mutate()}
        loading={mutationCheckGCalAuth.isLoading}
      >
        Check GCal Auth
      </Button>
      {mutationCheckGCalAuth.isSuccess && (
        <Alert message="Auth credentials are working" type="success" closable />
      )}
      {mutationCheckGCalAuth.isError && (
        <Alert
          message="Auth credentials are not working. Please refresh"
          type="error"
          closable
        />
      )}
      {authUrl && (
        <p>
          <a href={authUrl} target="_blank" rel="noreferrer">
            {authUrl}
          </a>
        </p>
      )}
      <Form
        form={form}
        onFinish={({ code }) => {
          mutationGCalRefreshToken.mutate({ params: { code: code } });
        }}
      >
        <Form.Item name="code" label="Code">
          <Input />
        </Form.Item>
        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={mutationGCalRefreshToken.isLoading}
          >
            Refresh Token
          </Button>
          {mutationGCalRefreshToken.isSuccess && (
            <Alert message="Refreshed token" type="success" />
          )}
          {mutationGCalRefreshToken.isError && (
            <Alert
              message={`Error: ${mutationGCalRefreshToken.error.message}`}
              type="error"
            />
          )}
        </Form.Item>
      </Form>
    </React.Fragment>
  );
};


