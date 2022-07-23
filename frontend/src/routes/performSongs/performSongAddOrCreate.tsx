import React, { useEffect, useState } from "react";
import { Alert, Button, Checkbox, DatePicker, Form, Input } from "antd";
import {
  useReadPerformSong,
  PerformSongRead,
  useUpdatePerformSong,
  useCreatePerformSong,
} from "../../api";
import { useSearchParams } from "react-router-dom";
import moment from "moment";

const { TextArea } = Input;

interface IPerformSongForm {
  performSong: PerformSongRead | undefined;
}

const PerformSongForm: React.FC<IPerformSongForm> = (props) => {
  const [form] = Form.useForm();
  const { performSong } = props;
  console.log(performSong);

  useEffect(() => {
    const vals: any = performSong;
    if (vals != null && vals.created_at != null) {
      console.log(vals.created_at);
      vals.created_at = moment(vals.created_at + "Z");
    }
    console.log(vals);
    // form.resetFields();
    form.setFieldsValue(vals);
  }, [form, performSong]);
  const mutationUpdatePerformSong = useUpdatePerformSong();
  const mutationCreatePerformSong = useCreatePerformSong();
  const onFinish = (values: any) => {
    if (performSong) {
      mutationUpdatePerformSong.mutate({
        performSongId: performSong.id,
        data: values,
      });
    } else {
      mutationCreatePerformSong.mutate({data: values});
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onFinish}
      // initialValues={initialValues}
    >
      <Form.Item name="name" label="Name" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="artist_name" label="Artist Name">
        <Input />
      </Form.Item>
      <Form.Item name="learned" label="Learned" valuePropName="checked">
        <Checkbox />
      </Form.Item>
      <Form.Item name="spotify_id" label="Spotify ID">
        <Input />
      </Form.Item>
      <Form.Item name="notes" label="Notes">
        <TextArea />
      </Form.Item>
      <Form.Item name="key" label="Key">
        <Input />
      </Form.Item>
      <Form.Item name="capo" label="Capo fret">
        <Input />
      </Form.Item>
      <Form.Item name="perform_url" label="Perform URL">
        <Input />
      </Form.Item>
      <Form.Item name="created_at" label="Created At">
        <DatePicker />
      </Form.Item>
      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          loading={
            mutationCreatePerformSong.isLoading ||
            mutationUpdatePerformSong.isLoading
          }
        >
          {performSong ? "Update" : "Submit"}
        </Button>
        {mutationCreatePerformSong.isSuccess && (
          <Alert message="song added" type="success" />
        )}
        {mutationUpdatePerformSong.isSuccess && (
          <Alert message="song updated" type="success" />
        )}
        {mutationCreatePerformSong.isError && (
          <Alert
            message={`Error: ${mutationCreatePerformSong.error.message}`}
            type="error"
          />
        )}
        {mutationUpdatePerformSong.isError && (
          <Alert
            message={`Error: ${mutationUpdatePerformSong.error.message}`}
            type="error"
          />
        )}
      </Form.Item>
    </Form>
  );
};

const PerformSongAddOrCreate: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const performSongId = searchParams.get("id");
  console.log(performSongId);
  const { data: performSong, isLoading } = useReadPerformSong(
    Number(performSongId),
    {
      query: { select: (d) => d.data },
    }
  );
  useEffect(() => console.log(performSong), [performSong]);
  // const { data } = useReadPerformSong();
  return <PerformSongForm performSong={performSong} />;
};

export { PerformSongAddOrCreate };
