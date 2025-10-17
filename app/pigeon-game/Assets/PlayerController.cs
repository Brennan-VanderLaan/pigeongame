using UnityEngine;

public class PlayerController : MonoBehaviour
{
    [Header("Movement")]
    public float moveForce = 100f;

    [Header("Camera")]
    public Transform playerCamera;
    public float mouseSensitivity = 0.1f;
    public float verticalLookLimit = 80f;

    private PlayerInputActions _inputActions;
    private PlayerInputActions inputActions
    {
        get
        {
            if (_inputActions == null)
                _inputActions = new PlayerInputActions();
            return _inputActions;
        }
    }
    private Rigidbody rb;
    private float cameraPitch = 0f;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        // Lock cursor to center of screen for FPS controls
        Cursor.lockState = CursorLockMode.Locked;
    }

    void OnEnable()
    {
        inputActions.Player.Enable();
    }

    
    void OnDisable()
    {
        inputActions.Player.Disable();
    }

    void Update()
    {
        Vector2 lookInput = inputActions.Player.Look.ReadValue<Vector2>();

        // Horizontal rotation (yaw) - rotate the player body
        float mouseX = lookInput.x * mouseSensitivity;
        transform.Rotate(Vector3.up * mouseX);

        // Vertical rotation (pitch) - rotate the camera
        if (playerCamera != null)
        {
            float mouseY = lookInput.y * mouseSensitivity;
            cameraPitch -= mouseY; // Subtract to invert Y axis (standard FPS controls)
            cameraPitch = Mathf.Clamp(cameraPitch, -verticalLookLimit, verticalLookLimit);
            playerCamera.localRotation = Quaternion.Euler(cameraPitch, 0f, 0f);
        }
    }


    void FixedUpdate() // Use FixedUpdate for physics!
    {
        Vector2 moveInput = inputActions.Player.Move.ReadValue<Vector2>();
        Vector3 movement = transform.right * moveInput.x + transform.forward * moveInput.y;
        rb.AddForce(movement * moveForce);
    }
}