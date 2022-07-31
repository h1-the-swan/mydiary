import { Alert, Button, Form, Input } from "antd";
import { useEffect } from "react";
import { useGetGCalAuthUrl, useRefreshGCalToken } from "../api";

const GCalRefreshToken = () => {
  const { data: authUrl } = useGetGCalAuthUrl({
    query: { select: (d) => d.data },
  });
  const mutationGCalRefreshToken = useRefreshGCalToken();
  const [form] = Form.useForm();
  return (
    <main>
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
    </main>
  );
};

export default GCalRefreshToken;
